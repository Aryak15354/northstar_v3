#!/usr/bin/env python3
"""
🎯 PORTFOLIO GOVERNOR - NORTHSTAR V3
Complete Portfolio Management System

This is the central portfolio management system that:
1. Loads market state and intelligence
2. Applies risk controls and exposure limits
3. Generates final portfolio weights
4. Ensures compliance with all constraints
5. Provides portfolio analytics for the trading desk

This is the GOVERNOR that ensures the portfolio obeys all rules.
"""

import pandas as pd
import numpy as np
import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import warnings
import logging
import yaml
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cohesion.bounded_exposure_calculator import BoundedExposureCalculator
from src.cohesion.state_file_manager import StateFileManager
from src.core.state import UnifiedState
from src.intelligence.dual_engine_coordinator import DualEngineCoordinator, MarketRegime
from src.data.loaders import load_regime_labels
from src.portfolio.governor import PortfolioGovernor as CapitalStructureGovernor

logger = logging.getLogger(__name__)


def _cap_aware_rescale(
    weights: "pd.Series",
    target_sum: float,
    position_cap: float,
    group_ids: "pd.Series" = None,
    group_cap: float = None,
    max_iterations: int = 25,
) -> "pd.Series":
    """
    Rescale/redistribute `weights` toward `target_sum` without letting any
    single weight exceed `position_cap`, or (if `group_ids`/`group_cap` are
    given) any group's summed weight exceed `group_cap`.

    A naive `weights / weights.sum() * target_sum` rescale -- used to be the
    final step of position/sector cap enforcement here -- silently pushes
    already-capped positions back over their cap whenever concentration is
    high enough that capped positions can't absorb the full redistribution
    (e.g. 3 positions all clipped to an 8% cap: sum=0.24, naive rescale to
    1.0 multiplies each back up to 0.333, 4x the intended cap). This instead
    only grows positions that still have headroom below their cap, and
    accepts a sum below `target_sum` once headroom is exhausted -- caps are
    a hard constraint, so an under-invested/cash residual is the correct
    outcome when they can't all be satisfied at full deployment, not a
    reason to violate them.
    """
    w = weights.astype(float).clip(lower=0.0)

    def _apply_caps(series: "pd.Series") -> "pd.Series":
        series = series.clip(upper=position_cap)
        if group_ids is not None and group_cap is not None and len(series) > 0:
            group_sums = series.groupby(group_ids).transform('sum')
            over = group_sums > group_cap
            if over.any():
                scale = (group_cap / group_sums).clip(upper=1.0)
                series = series * scale
        return series

    w = _apply_caps(w)

    for _ in range(max_iterations):
        gap = target_sum - w.sum()
        if gap <= 1e-9:
            break

        headroom = (position_cap - w).clip(lower=0.0)
        if group_ids is not None and group_cap is not None and len(w) > 0:
            group_sums = w.groupby(group_ids).transform('sum')
            group_headroom = (group_cap - group_sums).clip(lower=0.0)
            headroom = pd.concat([headroom, group_headroom], axis=1).min(axis=1)

        total_headroom = headroom.sum()
        if total_headroom <= 1e-9:
            break  # Fully capped: target_sum is not reachable without a violation.

        step = headroom / total_headroom * min(gap, total_headroom)
        w = _apply_caps(w + step)

    return w

class PortfolioGovernor:
    """
    Portfolio Governor - The Final Authority on Portfolio Construction
    
    This class orchestrates all portfolio management components and ensures
    the final portfolio complies with all risk and exposure constraints.
    """
    
    def __init__(self):
        self.name = "Northstar Portfolio Governor"
        self.version = "3.0"
        self.latest_capital_structure = None
        self.latest_capital_allocation_snapshot = {}
        # Equity regime authority must come from research regime labels.
        # Dual engine remains advisory-only for diagnostics/options context.
        requested_override = (
            str(os.getenv("NS_USE_DUAL_ENGINE_OVERRIDE", "0")).strip().lower()
            in {"1", "true", "yes", "on"}
        )
        if requested_override:
            print(
                "   ⚠️ NS_USE_DUAL_ENGINE_OVERRIDE requested but ignored for equity sizing; "
                "regime authority is research labels."
            )
        self.use_dual_engine_override = False
        self.live_policy_path = os.getenv("NS_POLICY_CONFIG", "config/research_policy.yaml")
        self.live_policy = self._load_live_policy(self.live_policy_path)
        defaults_cfg = self.live_policy.get("defaults", {})
        opportunity_cfg = self.live_policy.get("opportunity", {})
        overlay_cfg = self.live_policy.get("regime_overlays", {})
        signal_blend_cfg = self.live_policy.get("signal_blend", {})
        deployment_cfg = self.live_policy.get("deployment", {})

        self.canonical_regime_labels_path = str(
            self.live_policy.get("regime_labels_path", "data/processed/regime_labels.parquet")
        )
        self.default_allowed_exposure = self._as_float(defaults_cfg.get("allowed_exposure"), 0.60)
        self.default_risk_on_prob = self._as_float(defaults_cfg.get("risk_on_probability"), 0.50)
        self.default_freeze_exposure_cap = self._as_float(defaults_cfg.get("freeze_exposure_cap"), 0.15)
        self.risk_on_threshold = self._as_float(defaults_cfg.get("risk_on_threshold"), 0.70)
        self.risk_off_threshold = self._as_float(defaults_cfg.get("risk_off_threshold"), 0.30)
        self.max_positions_risk_on = self._as_int(defaults_cfg.get("max_positions_risk_on"), 25)
        self.max_positions_neutral = self._as_int(defaults_cfg.get("max_positions_neutral"), 30)
        self.max_positions_risk_off = self._as_int(defaults_cfg.get("max_positions_risk_off"), 40)
        self.concentration_center = self._as_float(defaults_cfg.get("concentration_center"), 0.50)
        self.concentration_scale = self._as_float(defaults_cfg.get("concentration_scale"), 2.00)
        self.estimated_portfolio_vol = self._as_float(
            defaults_cfg.get("estimated_portfolio_volatility"), 0.20
        )
        self.target_portfolio_vol = self._as_float(
            defaults_cfg.get("target_portfolio_volatility"), 0.15
        )

        self.opp_mispricing_weight = self._as_float(opportunity_cfg.get("mispricing_weight"), 0.60)
        self.opp_confirmation_weight = self._as_float(opportunity_cfg.get("confirmation_weight"), 0.40)
        self.opp_legacy_weight = self._as_float(opportunity_cfg.get("legacy_weight"), 0.75)
        self.opp_macro_weight = self._as_float(opportunity_cfg.get("macro_weight"), 0.25)
        self.opp_valuation_weight = self._as_float(opportunity_cfg.get("valuation_weight"), 0.20)
        self.opp_cohesive_weight = self._as_float(opportunity_cfg.get("cohesive_weight"), 0.10)
        self.opp_macro_default_rank = self._as_float(opportunity_cfg.get("macro_default_rank"), 0.50)
        self.opp_multiplier_base = self._as_float(opportunity_cfg.get("multiplier_base"), 0.80)
        self.opp_multiplier_span = self._as_float(opportunity_cfg.get("multiplier_span"), 0.70)
        self.opp_multiplier_min = self._as_float(opportunity_cfg.get("multiplier_min"), 0.80)
        self.opp_multiplier_max = self._as_float(opportunity_cfg.get("multiplier_max"), 1.50)

        self.selection_base_weight = self._as_float(signal_blend_cfg.get("base_score_weight"), 0.50)
        self.selection_cohesive_weight = self._as_float(signal_blend_cfg.get("cohesive_alpha_weight"), 0.20)
        self.selection_valuation_weight = self._as_float(signal_blend_cfg.get("valuation_weight"), 0.30)
        self.signal_min_overlay_coverage = self._as_int(signal_blend_cfg.get("min_overlay_coverage"), 25)

        self.deployment_floor_enabled = bool(deployment_cfg.get("enabled", True))
        self.deployment_floor_fill_ratio = self._as_float(deployment_cfg.get("governor_fill_ratio"), 0.35)
        self.deployment_floor_max_exposure = self._as_float(deployment_cfg.get("max_floor_exposure"), 0.60)
        self.deployment_floor_risk_on_min = self._as_float(deployment_cfg.get("risk_on_floor"), 0.45)
        blocklist = deployment_cfg.get(
            "regime_blocklist",
            ["crisis", "panic", "hostile", "slowdown", "tightening", "bear"],
        )
        self.deployment_floor_regime_blocklist = {
            self._normalize_regime_label(item) for item in blocklist if str(item).strip()
        }

        self.crisis_quality_boost = self._as_float(overlay_cfg.get("crisis_quality_boost"), 1.20)
        self.expansion_growth_boost = self._as_float(overlay_cfg.get("expansion_growth_boost"), 1.10)
        self.capital_structure_governor = self._initialize_capital_structure_governor()
        
        # Initialize state management components
        self.exposure_calculator = BoundedExposureCalculator()
        self.state_manager = StateFileManager()
        
        # Initialize dual engine coordinator
        self.dual_engine_coordinator = DualEngineCoordinator()
        
        # File paths
        self.paths = {
            'market_state': 'data/processed/market_state.parquet',
            'intelligent_state': 'data/processed/intelligent_market_state.parquet',
            'scores': 'data/processed/scores.parquet',
            'opportunity_surface': 'data/processed/opportunity_surface.parquet',
            'macro_conditioned_snapshot': 'data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet',
            'risk_budget': 'data/macro/factors/risk_budget.parquet',
            'output': 'data/processed/portfolio_weights.parquet',
            'analytics': 'data/processed/portfolio_analytics.json',
            'model_freeze_state': 'data/processed/model_freeze_state.json',
        }
        
        # Risk constraints (single source: config/research_policy.yaml::live_scoring.portfolio_governor.constraints)
        default_constraints = {
            'max_single_position': 0.08,
            'max_sector_exposure': 0.30,
            'max_total_exposure': 0.95,
            'min_diversification': 15,
            'max_turnover': 0.25,
            'cash_buffer': 0.05,
        }
        cfg_constraints = self.live_policy.get("constraints", {})
        self.constraints = {
            'max_single_position': self._as_float(
                cfg_constraints.get('max_single_position'),
                default_constraints['max_single_position']
            ),
            'max_sector_exposure': self._as_float(
                cfg_constraints.get('max_sector_exposure'),
                default_constraints['max_sector_exposure']
            ),
            'max_total_exposure': self._as_float(
                cfg_constraints.get('max_total_exposure'),
                default_constraints['max_total_exposure']
            ),
            'min_diversification': self._as_int(
                cfg_constraints.get('min_diversification'),
                default_constraints['min_diversification']
            ),
            'max_turnover': self._as_float(
                cfg_constraints.get('max_turnover'),
                default_constraints['max_turnover']
            ),
            'cash_buffer': self._as_float(
                cfg_constraints.get('cash_buffer'),
                default_constraints['cash_buffer']
            ),
        }
        
        # Portfolio roles
        self.position_roles = {
            'Core': 'Long-term conviction positions',
            'Satellite': 'Tactical allocation positions', 
            'Hedge': 'Risk mitigation positions',
            'Momentum': 'Trend-following positions',
            'Value': 'Contrarian value positions',
            'Quality': 'High-quality defensive positions'
        }

    def _initialize_capital_structure_governor(self):
        """Bootstrap the canonical Gap 6 governor for budget authority."""
        config_path = Path("config/portfolio_governor_config.yaml")
        config = {"starting_capital_inr": 10_000_000, "portfolio_governor": {}}
        if config_path.exists():
            try:
                payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                if isinstance(payload, dict):
                    config["portfolio_governor"] = payload
                    config["starting_capital_inr"] = payload.get("starting_capital_inr", config["starting_capital_inr"])
            except Exception:
                logger.exception("Failed loading canonical portfolio governor config: %s", config_path)
        try:
            return CapitalStructureGovernor(config=config)
        except Exception:
            logger.exception("Failed initializing canonical capital-structure governor")
            return None

    @staticmethod
    def _iter_open_option_positions(payload):
        if isinstance(payload, dict):
            positions = payload.get("open_positions", {})
            if isinstance(positions, dict):
                return [dict(pos or {}) for pos in positions.values()]
            if isinstance(positions, list):
                return [dict(pos or {}) for pos in positions]
        return []

    def _get_options_notional_deployed(self) -> float:
        path = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
        if not path.exists():
            return 0.0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            total = 0.0
            for position in self._iter_open_option_positions(payload):
                for key in ("notional", "max_loss", "current_value", "entry_credit_debit"):
                    value = pd.to_numeric(position.get(key), errors="coerce")
                    if pd.notna(value):
                        total += float(abs(value))
                        break
            return float(total)
        except Exception as exc:
            logger.warning("Could not read options runtime notional: %s", exc)
            return 0.0

    @staticmethod
    def _as_float(value, default):
        if value is None:
            return float(default)
        try:
            return float(value)
        except Exception:
            logger.exception("Invalid float config value: %r", value)
            raise

    @staticmethod
    def _as_int(value, default):
        if value is None:
            return int(default)
        try:
            return int(value)
        except Exception:
            logger.exception("Invalid int config value: %r", value)
            raise

    def _load_live_policy(self, config_path: str) -> dict:
        """Load live scoring policy for portfolio governor."""
        path = Path(config_path)
        if not path.exists():
            return {}
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            logger.exception("Failed loading portfolio live policy: %s", path)
            raise
        if not isinstance(payload, dict):
            return {}
        live_scoring = payload.get("live_scoring", {})
        if not isinstance(live_scoring, dict):
            return {}
        governor_cfg = live_scoring.get("portfolio_governor", {})
        return governor_cfg if isinstance(governor_cfg, dict) else {}

    def _load_canonical_regime_label(self) -> str:
        """Read today's regime from the canonical research regime labels file."""
        default_regime = "low_vol|uptrend|expansion"
        path = self.canonical_regime_labels_path

        try:
            labels = load_regime_labels(config_path=self.live_policy_path)
            if labels.empty:
                raise ValueError("regime_labels_empty")

            date_col = "date" if "date" in labels.columns else ("Date" if "Date" in labels.columns else None)
            if date_col is None or "regime" not in labels.columns:
                raise ValueError("regime_labels_missing_columns")

            labels[date_col] = pd.to_datetime(labels[date_col], errors="coerce").dt.normalize()
            today = pd.Timestamp.today().normalize()
            today_rows = labels[labels[date_col] == today].copy()
            if today_rows.empty:
                historical = labels[labels[date_col] <= today].copy()
                historical = historical.dropna(subset=[date_col]).sort_values(date_col, kind="mergesort")
                if not historical.empty:
                    fallback_row = historical.iloc[-1]
                    fallback_regime = str(fallback_row.get("regime", "") or "").strip()
                    fallback_date = pd.to_datetime(fallback_row.get(date_col), errors="coerce")
                    if fallback_regime:
                        print(
                            f"   ⚠️ No regime label for {today.date()} in {path}; "
                            f"using latest available label from {fallback_date.date()}: {fallback_regime}"
                        )
                        return fallback_regime
                print(
                    f"   ⚠️ No regime label for {today.date()} in {path}; "
                    f"falling back to {default_regime}"
                )
                return default_regime

            regime = str(today_rows["regime"].iloc[-1]).strip()
            if not regime:
                raise ValueError("regime_label_blank")
            return regime
        except FileNotFoundError:
            print(
                f"   ⚠️ Regime labels file missing ({path}); "
                f"falling back to {default_regime}"
            )
            return default_regime
        except Exception as e:
            print(
                f"   ⚠️ Failed to load canonical regime labels ({e}); "
                f"falling back to {default_regime}"
            )
            return default_regime

    def _load_canonical_unified_state(self):
        """Load the canonical UnifiedState snapshot for Gap 6 budget decisions."""
        state = UnifiedState()
        state_path = Path(state.state_file)

        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8") as handle:
                    state.load_snapshot(json.load(handle))
            except Exception:
                logger.exception("Failed loading canonical unified state snapshot: %s", state_path)

        # Fill any still-empty sections from legacy sources as a compatibility fallback.
        if state.market.regime == "unknown":
            state.load_from_legacy_sources()

        return state

    def _apply_canonical_capital_structure(self, intelligence):
        """
        Replace legacy exposure authority with the canonical Gap 6 Governor decision.

        The legacy portfolio constructor still builds weights, but top-level exposure
        now comes only from the canonical capital structure governor.
        """
        if self.capital_structure_governor is None:
            return intelligence

        try:
            unified_state = self._load_canonical_unified_state()
            structure = self.capital_structure_governor.compute_capital_structure(unified_state)
            if structure is None:
                print("   ⚠️ Canonical Governor refused to compute on stale unified state")
                return intelligence
            self.latest_capital_structure = structure.to_dict()
            previous_allowed = self._as_float(
                intelligence.get("allowed_exposure"),
                self.default_allowed_exposure,
            )
            structure_equity = float(structure.equity_fraction)
            intelligence["legacy_allowed_exposure"] = previous_allowed
            intelligence["allowed_exposure"] = min(previous_allowed, structure_equity)
            intelligence["capital_structure"] = self.latest_capital_structure
            intelligence["capital_structure_regime"] = structure.capital_structure_regime.value
            intelligence["equity_budget_inr"] = float(structure.equity_budget_inr)
            intelligence["options_budget_inr"] = float(structure.options_budget_inr)
            intelligence["cash_reserve_inr"] = float(structure.cash_reserve_inr)
            intelligence["options_notional_deployed"] = float(self._get_options_notional_deployed())
            intelligence["governor_primary_rationale"] = structure.primary_rationale
            print(
                "   🏛️ Canonical Governor budget: "
                f"{structure.capital_structure_regime.value} "
                f"(equity={structure.equity_fraction:.1%}, options={structure.options_fraction:.1%}, cash={structure.cash_fraction:.1%})"
            )
            if intelligence["allowed_exposure"] < structure_equity:
                print(
                    "   🛡️ Exposure clamp preserved tighter live limit: "
                    f"{structure_equity:.1%} -> {intelligence['allowed_exposure']:.1%}"
                )
        except Exception as exc:
            logger.exception("Failed applying canonical capital structure")
            print(f"   ⚠️ Could not apply canonical capital structure: {exc}")

        return intelligence

    def _apply_allocator_exposure_constraints(self, intelligence):
        """Clamp final exposure to the allocator / NO_EDGE envelope.

        The strategy-layer allocator contributes a hard exposure cap, but it should not
        force the core equity book to mirror the sum of live strategy sleeve weights.
        """
        snapshot = self.latest_capital_allocation_snapshot or {}
        if not isinstance(snapshot, dict) or not snapshot:
            return intelligence

        def _ratio(value):
            parsed = pd.to_numeric(value, errors='coerce')
            if pd.isna(parsed):
                return None
            out = float(parsed)
            if out > 1.0 and out <= 100.0:
                out = out / 100.0
            if not np.isfinite(out):
                return None
            return max(0.0, min(1.0, out))

        allocations = intelligence.get('capital_allocations', {}) or {}
        total_exposure = _ratio(snapshot.get('total_exposure'))
        if total_exposure is None and isinstance(allocations, dict) and allocations:
            total_exposure = _ratio(sum(float(v or 0.0) for v in allocations.values()))

        no_edge_state = snapshot.get('no_edge_state', {}) if isinstance(snapshot.get('no_edge_state'), dict) else {}
        exposure_cap = _ratio(snapshot.get('exposure_cap'))
        if exposure_cap is None:
            exposure_cap = _ratio(no_edge_state.get('exposure_cap'))
        effective_exposure_cap = _ratio(snapshot.get('effective_exposure_cap'))
        if effective_exposure_cap is None:
            effective_exposure_cap = exposure_cap
        enforce_total_exposure_as_cap = bool(snapshot.get('enforce_total_exposure_as_cap', False))

        intelligence['capital_allocator_total_exposure'] = total_exposure
        intelligence['capital_allocator_exposure_cap'] = exposure_cap
        intelligence['capital_allocator_effective_exposure_cap'] = effective_exposure_cap
        intelligence['capital_allocator_no_edge_state'] = no_edge_state

        current_allowed = self._as_float(
            intelligence.get('allowed_exposure'),
            self.default_allowed_exposure,
        )
        capped_allowed = current_allowed
        if enforce_total_exposure_as_cap and total_exposure is not None:
            capped_allowed = min(capped_allowed, total_exposure)
        if effective_exposure_cap is not None:
            capped_allowed = min(capped_allowed, effective_exposure_cap)

        if capped_allowed < current_allowed:
            print(f"   🧮 Capital allocator clamp: {current_allowed:.1%} -> {capped_allowed:.1%}")
        intelligence['allowed_exposure'] = capped_allowed
        return intelligence

    def _apply_governor_deployment_floor(self, intelligence):
        """
        Ensure we do not under-deploy in supportive conditions when the governor budget
        is materially above the legacy exposure control.
        """
        if not self.deployment_floor_enabled:
            return intelligence
        if bool((intelligence.get('freeze_state') or {}).get('freeze_active', False)):
            return intelligence

        no_edge_state = intelligence.get('capital_allocator_no_edge_state', {}) or {}
        if str(no_edge_state.get('state', 'NORMAL')).upper() == 'NO_EDGE':
            return intelligence

        regime_label = self._normalize_regime_label(intelligence.get('regime', 'unknown'))
        if any(token in regime_label for token in self.deployment_floor_regime_blocklist):
            return intelligence

        risk_on_prob = self._as_float(intelligence.get('risk_on_prob'), self.default_risk_on_prob)
        if risk_on_prob < self.deployment_floor_risk_on_min:
            return intelligence

        capital_structure = intelligence.get('capital_structure', {}) or {}
        equity_fraction = pd.to_numeric(capital_structure.get('equity_fraction'), errors='coerce')
        if pd.isna(equity_fraction) or float(equity_fraction) <= 0.0:
            return intelligence

        target_floor = min(
            float(equity_fraction) * self.deployment_floor_fill_ratio,
            self.deployment_floor_max_exposure,
            float(equity_fraction),
        )
        current_allowed = self._as_float(
            intelligence.get('allowed_exposure'),
            self.default_allowed_exposure,
        )
        intelligence['governor_deployment_floor'] = target_floor
        if target_floor > current_allowed:
            intelligence['legacy_allowed_exposure'] = current_allowed
            intelligence['allowed_exposure'] = target_floor
            print(
                "   🏛️ Governor deployment floor applied: "
                f"{current_allowed:.1%} -> {target_floor:.1%}"
            )
        return intelligence
    
    def load_market_intelligence(self):
        """Load market state and AI intelligence with dual engine coordination"""
        
        print("🧠 Loading market intelligence with dual engine coordination...")
        
        intelligence = {
            'market_state': {},
            'ai_intelligence': {},
            'regime': self._load_canonical_regime_label(),
            'allowed_exposure': self.default_allowed_exposure,
            'risk_on_prob': self.default_risk_on_prob,
            'ai_active': False,
            'strategy_performance': {},
            'capital_allocations': {},
            'freeze_state': {'freeze_active': False, 'actions': {}},
            'freeze_active': False,
            'freeze_actions': {},
            'engine_allocation': None,
            'engine_recommended_regime': None,
            'engine_recommended_exposure': None,
            'regime_authority': 'research_regime_labels',
            'regime_alignment': 'unknown',
            'crisis_engine_active': False,
            'trend_engine_active': False
        }
        
        # Load market state using StateFileManager
        try:
            market_df = self.state_manager.read_market_state()
            if not market_df.empty:
                latest_market = market_df.iloc[-1]
                intelligence['market_state'] = latest_market.to_dict()
                
                # Read allowed_exposure from canonical source.
                # Some upstream artifacts store as [0,1], others as [0,100].
                allowed_exposure = pd.to_numeric(
                    latest_market.get('allowed_exposure', self.default_allowed_exposure), errors='coerce'
                )
                if pd.isna(allowed_exposure):
                    allowed_exposure = self.default_allowed_exposure
                allowed_exposure = float(allowed_exposure)
                if allowed_exposure > 1.0:
                    allowed_exposure = allowed_exposure / 100.0
                if not (0.0 <= allowed_exposure <= 1.0):
                    print(f"   ⚠️ Invalid allowed_exposure {allowed_exposure}, bounding to [0.0, 1.0]")
                    allowed_exposure = max(0.0, min(1.0, allowed_exposure))
                
                intelligence['allowed_exposure'] = allowed_exposure
                intelligence['risk_on_prob'] = self._as_float(
                    latest_market.get('risk_on', self.default_risk_on_prob),
                    self.default_risk_on_prob,
                )
                print(f"   ✅ Market state loaded (regime authority: {intelligence['regime_authority']})")
                print(f"   🧭 Canonical regime: {intelligence['regime']}")
                print(f"   📊 Allowed Exposure: {intelligence['allowed_exposure']:.1%}")
        except FileNotFoundError:
            print(f"   ⚠️ Market state file not found, using defaults")
        except Exception as e:
            print(f"   ⚠️ Could not load market state: {e}")
        
        # Load AI intelligence if available
        try:
            if os.path.exists(self.paths['intelligent_state']):
                ai_df = pd.read_parquet(self.paths['intelligent_state'])
                if not ai_df.empty:
                    latest_ai = ai_df.iloc[-1]
                    intelligence['ai_intelligence'] = latest_ai.to_dict()
                    intelligence['ai_active'] = latest_ai.get('intelligence_status') == 'active'

                    # Always respect canonical intelligent market-state controls when present.
                    # Values in this artifact may be stored either as [0,1] or [0,100].
                    allowed_exposure = pd.to_numeric(latest_ai.get('allowed_exposure'), errors='coerce')
                    if pd.notna(allowed_exposure):
                        allowed_exposure = float(allowed_exposure)
                        if allowed_exposure > 1.0:
                            allowed_exposure = allowed_exposure / 100.0
                        intelligence['allowed_exposure'] = max(0.0, min(1.0, allowed_exposure))

                    risk_on_prob = pd.to_numeric(latest_ai.get('risk_on_probability'), errors='coerce')
                    if pd.notna(risk_on_prob):
                        risk_on_prob = float(risk_on_prob)
                        if risk_on_prob > 1.0:
                            risk_on_prob = risk_on_prob / 100.0
                        intelligence['risk_on_prob'] = max(0.0, min(1.0, risk_on_prob))

                    regime_ai = latest_ai.get('regime_ai')
                    if isinstance(regime_ai, str) and regime_ai.strip():
                        intelligence['ai_regime'] = regime_ai.strip().lower()
                    
                    # Override with AI recommendations if available
                    if intelligence['ai_active']:
                        ai_exposure = latest_ai.get('ai_allowed_exposure')
                        ai_exposure = pd.to_numeric(ai_exposure, errors='coerce')
                        if pd.notna(ai_exposure):
                            ai_exposure = float(ai_exposure)
                            if ai_exposure > 1.0:
                                ai_exposure = ai_exposure / 100.0
                            intelligence['allowed_exposure'] = max(0.0, min(1.0, ai_exposure))
                        
                        ai_risk_on = latest_ai.get('ai_risk_on_probability')
                        ai_risk_on = pd.to_numeric(ai_risk_on, errors='coerce')
                        if pd.notna(ai_risk_on):
                            ai_risk_on = float(ai_risk_on)
                            if ai_risk_on > 1.0:
                                ai_risk_on = ai_risk_on / 100.0
                            intelligence['risk_on_prob'] = max(0.0, min(1.0, ai_risk_on))
                        
                        print(f"   🤖 AI intelligence active: {intelligence['allowed_exposure']:.1%} exposure")
                    else:
                        print(
                            f"   🧭 Intelligent state loaded: "
                            f"exposure={intelligence['allowed_exposure']:.1%}, "
                            f"risk_on={intelligence['risk_on_prob']:.1%}"
                        )
        except Exception as e:
            print(f"   ⚠️ Could not load AI intelligence: {e}")

        # Load institutional freeze state (if active, exposure/risk must be constrained).
        try:
            freeze_path = self.paths.get('model_freeze_state')
            if freeze_path and os.path.exists(freeze_path):
                with open(freeze_path, 'r') as f:
                    freeze_state = json.load(f)
                if isinstance(freeze_state, dict):
                    intelligence['freeze_state'] = freeze_state
                    intelligence['freeze_active'] = bool(freeze_state.get('freeze_active', False))
                    intelligence['freeze_actions'] = freeze_state.get('actions', {}) or {}
                    if intelligence['freeze_active']:
                        cap = self._as_float(
                            intelligence['freeze_actions'].get('target_max_exposure'),
                            self.default_freeze_exposure_cap,
                        )
                        prev = self._as_float(
                            intelligence.get('allowed_exposure'),
                            self.default_allowed_exposure,
                        )
                        intelligence['allowed_exposure'] = min(prev, cap)
                        print(
                            f"   🧊 Freeze active: allowed exposure "
                            f"{prev:.1%} -> {intelligence['allowed_exposure']:.1%}"
                        )
        except Exception as e:
            print(f"   ⚠️ Could not load freeze state: {e}")
        
        # Load strategy performance data
        intelligence['strategy_performance'] = self.load_strategy_performance()
        
        # Load capital allocations
        intelligence['capital_allocations'] = self.load_capital_allocations()
        
        # Coordinate dual engines based on market data
        market_data = self.prepare_market_data_for_engines(intelligence)
        if market_data is not None and not market_data.empty:
            current_date = datetime.now()
            engine_allocation = self.dual_engine_coordinator.coordinate_engine_allocations(
                market_data, current_date
            )
            
            intelligence['engine_allocation'] = engine_allocation
            intelligence['crisis_engine_active'] = engine_allocation.crisis_allocation > 0
            intelligence['trend_engine_active'] = engine_allocation.trend_allocation > 0
            intelligence['engine_recommended_exposure'] = engine_allocation.total_allocation
            intelligence['engine_recommended_regime'] = engine_allocation.regime.value.lower()

            is_synthetic_source = bool(getattr(market_data, 'attrs', {}).get('synthetic', False))
            if not is_synthetic_source and self.use_dual_engine_override:
                # Explicit override mode only.
                intelligence['allowed_exposure'] = engine_allocation.total_allocation
                intelligence['regime'] = engine_allocation.regime.value.lower()
                intelligence['regime_authority'] = 'dual_engine_override'

            canonical_regime = str(intelligence.get('regime', 'neutral'))
            engine_regime = str(engine_allocation.regime.value.lower())
            canonical_norm = self._normalize_regime_label(canonical_regime)
            engine_norm = self._normalize_regime_label(engine_regime)
            intelligence['regime_alignment'] = 'aligned' if canonical_norm == engine_norm else 'mismatch'

            print(f"   🎯 Engine Coordination:")
            print(f"      Active Engine: {engine_allocation.active_engine}")
            print(f"      Market Regime: {engine_allocation.regime.value}")
            print(f"      Total Allocation: {engine_allocation.total_allocation:.1%}")
            if self.use_dual_engine_override:
                print("      Authority: dual_engine_override (enabled)")
            else:
                print("      Authority: intelligent_market_state (engine advisory)")
            if is_synthetic_source:
                print("      ⚠️ Synthetic engine input detected - preserving canonical exposure controls")
            if intelligence['regime_alignment'] != 'aligned':
                print(
                    f"      ⚠️ Regime mismatch: canonical={canonical_regime}, "
                    f"engine={engine_regime}"
                )
            
            if engine_allocation.crisis_allocation > 0:
                print(f"      🔥 Crisis Engine: {engine_allocation.crisis_allocation:.1%}")
            if engine_allocation.trend_allocation > 0:
                print(f"      📈 Trend Engine: {engine_allocation.trend_allocation:.1%}")
        else:
            print(f"   ⚠️ No market data available for engine coordination")

        intelligence = self._apply_canonical_capital_structure(intelligence)
        intelligence = self._apply_allocator_exposure_constraints(intelligence)
        intelligence = self._apply_governor_deployment_floor(intelligence)
        return intelligence

    @staticmethod
    def _normalize_regime_label(label: str) -> str:
        """Map heterogeneous regime labels to a common coarse bucket."""
        s = str(label or "").replace("_", " ").replace("-", " ").strip().lower()
        if not s:
            return "unknown"
        if any(k in s for k in ["late expansion", "neutral", "recovery"]):
            return "neutral"
        if any(k in s for k in ["panic", "hostile", "crisis"]):
            return "crisis"
        if any(k in s for k in ["boom", "supportive", "expansion"]):
            return "expansion"
        if any(k in s for k in ["slowdown", "tightening", "bear"]):
            return "slowdown"
        return s
    
    def load_strategy_performance(self):
        """Load strategy performance metrics for decision making"""
        
        print("📊 Loading strategy performance...")
        
        performance = {}
        
        # Load from strategy performance directory
        perf_dir = 'data/processed/strategy_performance'
        if os.path.exists(perf_dir):
            summary_file = os.path.join(perf_dir, 'summary.json')
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r') as f:
                        performance = json.load(f)
                    print(f"   ✅ Loaded performance for {len(performance)} strategies")
                except Exception as e:
                    print(f"   ⚠️ Error loading strategy performance: {e}")
        
        # Load from backtests directory as fallback
        backtest_dir = 'data/processed/backtests'
        if not performance and os.path.exists(backtest_dir):
            for file in os.listdir(backtest_dir):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(backtest_dir, file))
                        if not df.empty and len(df) > 1:
                            returns = df['daily_return']
                            equity = df['equity']
                            
                            performance[strategy_name] = {
                                'total_return': equity.iloc[-1] - 1,
                                'ann_return': (equity.iloc[-1] ** (252 / len(df))) - 1,
                                'volatility': returns.std() * np.sqrt(252),
                                'sharpe': (returns.mean() * 252) / (returns.std() * np.sqrt(252)),
                                'max_drawdown': df['drawdown'].min(),
                                'win_rate': (returns > 0).mean(),
                                'last_return': returns.iloc[-1] if len(returns) > 0 else 0
                            }
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
            
            if performance:
                print(f"   ✅ Loaded performance from backtests: {len(performance)} strategies")
        
        return performance
    
    def load_capital_allocations(self):
        """Load current capital allocations across strategies"""
        
        allocations = {}
        self.latest_capital_allocation_snapshot = {}
        
        try:
            alloc_file = 'data/processed/capital_allocations.json'
            if os.path.exists(alloc_file):
                with open(alloc_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.latest_capital_allocation_snapshot = data
                    allocations = data.get('allocations', {})
                    print(f"   ✅ Loaded capital allocations: {len(allocations)} strategies")
        except Exception as e:
            print(f"   ⚠️ Could not load capital allocations: {e}")
        
        return allocations
    
    def prepare_market_data_for_engines(self, intelligence):
        """Prepare market data for dual engine coordination"""
        
        try:
            # Real-data-only market inputs for engine coordination.
            market_data = None

            def _tag(df, source):
                if df is None or df.empty:
                    return df
                df.attrs['source'] = source
                df.attrs['synthetic'] = False
                return df

            # Source 1: explicit return series artifacts (already real returns).
            if market_data is None:
                market_files = [
                    'data/processed/market_state.parquet',
                    'data/raw/market_index.csv',
                    'data/processed/market_returns.parquet'
                ]
                
                for file_path in market_files:
                    if os.path.exists(file_path):
                        try:
                            if file_path.endswith('.parquet'):
                                df = pd.read_parquet(file_path)
                            else:
                                df = pd.read_csv(file_path)
                            
                            # Look for return columns
                            return_cols = [c for c in df.columns if 'return' in c.lower()]
                            if return_cols and len(df) > 20:
                                series = pd.to_numeric(df[return_cols[0]], errors='coerce').dropna()
                                if len(series) > 20:
                                    if 'date' in df.columns:
                                        dates = pd.to_datetime(df['date'], errors='coerce')
                                    elif 'Date' in df.columns:
                                        dates = pd.to_datetime(df['Date'], errors='coerce')
                                    else:
                                        dates = pd.to_datetime(df.index, errors='coerce')
                                    tmp = pd.DataFrame({'date': dates, 'market_return': pd.to_numeric(df[return_cols[0]], errors='coerce')})
                                    tmp = tmp.dropna(subset=['date', 'market_return']).tail(260)
                                    if not tmp.empty:
                                        market_data = _tag(tmp, f"returns:{file_path}")
                                break
                        except Exception:
                            logger.exception("Failed reading market-return source: %s", file_path)
                            raise

            # Source 2: derive returns from trusted index close series.
            if market_data is None:
                for idx_path in [
                    'data/processed/nifty.parquet',
                    'data/processed/index_data/nifty_50.parquet',
                    'data/processed/index_data/nifty_100.parquet',
                    'data/processed/index_data/nifty_500.parquet',
                ]:
                    if not os.path.exists(idx_path):
                        continue
                    try:
                        idx = pd.read_parquet(idx_path)
                        if idx.empty:
                            continue
                        close_col = 'close' if 'close' in idx.columns else ('adj_close' if 'adj_close' in idx.columns else None)
                        if close_col is None:
                            continue
                        close = pd.to_numeric(idx[close_col], errors='coerce')
                        ret = close.pct_change().dropna()
                        if len(ret) < 20:
                            continue
                        dates = pd.to_datetime(ret.index, errors='coerce')
                        tmp = pd.DataFrame({'date': dates, 'market_return': ret.values}).dropna().tail(260)
                        if not tmp.empty:
                            market_data = _tag(tmp, f"index:{idx_path}")
                            break
                    except Exception:
                        logger.exception("Failed deriving returns from index source: %s", idx_path)
                        raise

            if market_data is None:
                print("   ⚠️ No real market-return series available for engine coordination")
                return None
            
            return market_data
            
        except Exception as e:
            print(f"   ⚠️ Error preparing market data: {e}")
            return None
    
    def load_universe_scores(self):
        """Load stock universe with scores and rankings"""
        
        print("📊 Loading stock universe...")
        
        try:
            if os.path.exists(self.paths['scores']):
                scores_df = pd.read_parquet(self.paths['scores'])
                scores_df = scores_df.copy()
                if 'ticker' in scores_df.columns:
                    scores_df['ticker'] = scores_df['ticker'].astype(str).str.strip()
                
                # Ensure we have required columns
                required_cols = ['ticker']
                score_cols = [c for c in ['northstar_score', 'final_score', 'score'] if c in scores_df.columns]
                
                if not score_cols:
                    print("   ⚠️ No score columns found, using equal weights")
                    scores_df['score'] = 1.0
                    score_col = 'score'
                else:
                    score_col = score_cols[0]
                
                # Clean and prepare data
                universe = scores_df[scores_df[score_col].notna()].copy()
                universe = universe.sort_values(score_col, ascending=False)
                
                # Add company names if available
                if 'Company Name' not in universe.columns:
                    universe['Company Name'] = universe['ticker']
                else:
                    company_name = universe['Company Name'].fillna('').astype(str).str.strip()
                    universe['Company Name'] = company_name.where(company_name.ne(''), universe['ticker'].astype(str))
                
                # Add industry if available
                if 'Industry' not in universe.columns:
                    if 'sector' in universe.columns:
                        universe['Industry'] = universe['sector']
                    else:
                        universe['Industry'] = 'Unknown'
                universe['Industry'] = universe['Industry'].fillna('Unknown').astype(str)

                # Enrich missing metadata from reference universe when scores are thin.
                try:
                    ref_path = Path('universe/nifty500.csv')
                    if ref_path.exists():
                        ref = pd.read_csv(ref_path)
                        ticker_col = next((c for c in ['Symbol', 'ticker', 'Ticker', 'symbol'] if c in ref.columns), None)
                        if ticker_col is not None:
                            ref = ref.copy()
                            ref['ticker'] = ref[ticker_col].astype(str).str.strip().str.upper()
                            ref['ticker'] = ref['ticker'].map(
                                lambda x: x if '.' in x else f"{x}.NS"
                            )
                            name_col = next(
                                (c for c in ['Company Name', 'company_name', 'Security Name'] if c in ref.columns),
                                None,
                            )
                            industry_col = next(
                                (c for c in ['Industry', 'industry', 'Sector', 'sector', 'Industry Name'] if c in ref.columns),
                                None,
                            )
                            keep_cols = ['ticker']
                            if name_col is not None:
                                keep_cols.append(name_col)
                            if industry_col is not None:
                                keep_cols.append(industry_col)
                            ref = ref[keep_cols].drop_duplicates('ticker', keep='last')
                            universe = universe.merge(ref, on='ticker', how='left', suffixes=('', '_ref'))
                            if name_col is not None:
                                ref_name_col = f'{name_col}_ref' if f'{name_col}_ref' in universe.columns else name_col
                                base_name = universe['Company Name'].fillna('').astype(str).str.strip()
                                ref_name = universe[ref_name_col].fillna('').astype(str).str.strip()
                                universe['Company Name'] = base_name.where(base_name.ne(''), ref_name)
                            if industry_col is not None:
                                ref_industry_col = f'{industry_col}_ref' if f'{industry_col}_ref' in universe.columns else industry_col
                                base_industry = universe['Industry'].fillna('').astype(str).str.strip()
                                ref_industry = universe[ref_industry_col].fillna('Unknown').astype(str).str.strip()
                                missing_industry = base_industry.eq('') | base_industry.eq('Unknown') | base_industry.eq('nan')
                                universe['Industry'] = base_industry.where(~missing_industry, ref_industry)
                            drop_cols = [c for c in universe.columns if c.endswith('_ref')]
                            universe = universe.drop(columns=drop_cols, errors='ignore')
                except Exception as exc:
                    print(f"   ⚠️ Metadata enrichment skipped: {exc}")

                universe = self._enrich_universe_with_research_signals(universe, score_col)
                if 'selection_score' in universe.columns:
                    overlay_cols = [
                        col for col in ['cohesive_alpha_rank_score', 'valuation_signal']
                        if col in universe.columns
                    ]
                    overlay_hits = int(universe[overlay_cols].notna().any(axis=1).sum()) if overlay_cols else 0
                    if overlay_hits >= self.signal_min_overlay_coverage:
                        score_col = 'selection_score'
                        universe = universe.sort_values(score_col, ascending=False, kind='mergesort')
                        print(
                            f"   🧠 Research signal blend active: {overlay_hits}/{len(universe)} "
                            "tickers with valuation/cohesive coverage"
                        )
                    else:
                        print(
                            f"   ⚠️ Research signal coverage too thin for ranking override: "
                            f"{overlay_hits}/{len(universe)}"
                        )
                
                print(f"   ✅ Universe loaded: {len(universe)} stocks")
                return universe, score_col
                
        except Exception as e:
            print(f"   ❌ Error loading universe: {e}")
        
        # Fallback empty universe with standardized column names
        return pd.DataFrame(columns=['ticker', 'score', 'company_name', 'industry']), 'score'
    
    def load_opportunity_surface(self):
        """Load opportunity surface for enhanced position sizing"""
        
        print("🎯 Loading opportunity surface...")
        
        try:
            if os.path.exists(self.paths['opportunity_surface']):
                opp_df = pd.read_parquet(self.paths['opportunity_surface'])
                
                if not opp_df.empty and 'mispricing' in opp_df.columns:
                    print(f"   ✅ Opportunity surface loaded: {len(opp_df)} opportunities")
                    return opp_df
                    
        except Exception as e:
            print(f"   ⚠️ Could not load opportunity surface: {e}")
        
        return pd.DataFrame()

    @staticmethod
    def _cross_section_rank(series: pd.Series, neutral: float = 0.50) -> pd.Series:
        values = pd.to_numeric(series, errors='coerce')
        if values.notna().sum() <= 1:
            return pd.Series(neutral, index=series.index, dtype=float)
        ranked = values.rank(pct=True, method='average')
        return ranked.fillna(neutral).clip(lower=0.0, upper=1.0)

    def _load_research_signal_overlay(self) -> pd.DataFrame:
        """Load cohesive alpha and valuation signals for stock-selection blending."""
        frames = []

        cohesive_path = Path('data/processed/cohesive_alpha_feed.parquet')
        if cohesive_path.exists():
            try:
                cohesive = pd.read_parquet(cohesive_path)
                if not cohesive.empty and 'ticker' in cohesive.columns:
                    cohesive = cohesive.copy()
                    cohesive['ticker'] = cohesive['ticker'].astype(str).str.strip()
                    if 'cohesive_alpha_score' not in cohesive.columns:
                        cohesive['cohesive_alpha_score'] = np.nan
                    cohesive['cohesive_alpha_score'] = pd.to_numeric(
                        cohesive['cohesive_alpha_score'], errors='coerce'
                    )
                    cohesive['cohesive_alpha_rank_score'] = self._cross_section_rank(
                        cohesive['cohesive_alpha_score']
                    )
                    frames.append(
                        cohesive[['ticker', 'cohesive_alpha_score', 'cohesive_alpha_rank_score']]
                        .drop_duplicates('ticker', keep='last')
                    )
            except Exception as exc:
                print(f"   ⚠️ Cohesive alpha overlay unavailable: {exc}")

        valuation_path = Path('data/processed/valuation.parquet')
        if valuation_path.exists():
            try:
                valuation = pd.read_parquet(valuation_path)
                if not valuation.empty and 'ticker' in valuation.columns:
                    valuation = valuation.copy()
                    valuation['ticker'] = valuation['ticker'].astype(str).str.strip()
                    mos_col = (
                        'dcf_margin_of_safety_v2_pct'
                        if 'dcf_margin_of_safety_v2_pct' in valuation.columns
                        else 'margin_of_safety_pct'
                    )
                    if mos_col not in valuation.columns:
                        valuation[mos_col] = np.nan
                    valuation['margin_of_safety_pct'] = pd.to_numeric(
                        valuation[mos_col], errors='coerce'
                    ).clip(lower=0.0, upper=1.0)

                    owner_yield_col = (
                        'owner_earnings_yield_v2'
                        if 'owner_earnings_yield_v2' in valuation.columns
                        else 'owner_earnings_yield'
                    )
                    if owner_yield_col not in valuation.columns:
                        valuation[owner_yield_col] = np.nan
                    owner_yield = pd.to_numeric(valuation[owner_yield_col], errors='coerce')
                    if owner_yield.notna().sum() > 5:
                        lower = owner_yield.quantile(0.01)
                        upper = owner_yield.quantile(0.99)
                        owner_yield = owner_yield.clip(lower=lower, upper=upper)
                    valuation['owner_earnings_yield_v2'] = owner_yield
                    valuation['owner_earnings_rank_score'] = self._cross_section_rank(owner_yield)
                    valuation['valuation_signal'] = (
                        0.65 * valuation['margin_of_safety_pct'].fillna(0.50) +
                        0.35 * valuation['owner_earnings_rank_score'].fillna(0.50)
                    ).clip(lower=0.0, upper=1.0)
                    keep_cols = [
                        'ticker',
                        'margin_of_safety_pct',
                        'owner_earnings_yield_v2',
                        'owner_earnings_rank_score',
                        'valuation_signal',
                    ]
                    frames.append(valuation[keep_cols].drop_duplicates('ticker', keep='last'))
            except Exception as exc:
                print(f"   ⚠️ Valuation overlay unavailable: {exc}")

        if not frames:
            return pd.DataFrame()

        overlay = frames[0]
        for frame in frames[1:]:
            overlay = overlay.merge(frame, on='ticker', how='outer', suffixes=('', '_dup'))
            dup_cols = [c for c in overlay.columns if c.endswith('_dup')]
            overlay = overlay.drop(columns=dup_cols, errors='ignore')
        return overlay

    def _enrich_universe_with_research_signals(self, universe: pd.DataFrame, score_col: str) -> pd.DataFrame:
        if universe.empty or 'ticker' not in universe.columns:
            return universe

        overlay = self._load_research_signal_overlay()
        enriched = universe.copy()
        if overlay.empty:
            enriched['base_score_rank'] = self._cross_section_rank(enriched[score_col])
            enriched['selection_score'] = enriched['base_score_rank']
            return enriched

        enriched = enriched.merge(overlay, on='ticker', how='left')
        if 'Industry_x' in enriched.columns or 'Industry_y' in enriched.columns:
            base_col = 'Industry_x' if 'Industry_x' in enriched.columns else 'Industry'
            overlay_col = 'Industry_y' if 'Industry_y' in enriched.columns else None
            fallback_industry = enriched[base_col].fillna('Unknown').astype(str)
            overlay_industry = (
                enriched[overlay_col].fillna('Unknown').astype(str)
                if overlay_col is not None
                else pd.Series('Unknown', index=enriched.index)
            )
            missing = fallback_industry.eq('Unknown') | fallback_industry.eq('') | fallback_industry.eq('nan')
            enriched['Industry'] = fallback_industry.where(~missing, overlay_industry)
            enriched = enriched.drop(columns=['Industry_x', 'Industry_y'], errors='ignore')

        enriched['base_score_rank'] = self._cross_section_rank(enriched[score_col])
        cohesive_rank = pd.to_numeric(enriched.get('cohesive_alpha_rank_score'), errors='coerce').fillna(0.50)
        valuation_rank = pd.to_numeric(enriched.get('valuation_signal'), errors='coerce').fillna(0.50)

        total_weight = (
            self.selection_base_weight +
            self.selection_cohesive_weight +
            self.selection_valuation_weight
        )
        base_w = self.selection_base_weight / total_weight
        cohesive_w = self.selection_cohesive_weight / total_weight
        valuation_w = self.selection_valuation_weight / total_weight
        enriched['selection_score'] = (
            base_w * enriched['base_score_rank'] +
            cohesive_w * cohesive_rank +
            valuation_w * valuation_rank
        ).clip(lower=0.0, upper=1.0)
        return enriched

    def load_macro_conditioned_snapshot(self):
        """
        Load latest macro-conditioned cross-sectional signal snapshot.
        This conditions opportunity sizing on RBI+market state.
        """
        print("🧠 Loading macro-conditioned signal snapshot...")

        try:
            path = self.paths.get('macro_conditioned_snapshot')
            if not path or not os.path.exists(path):
                print("   ⚠️ Macro-conditioned snapshot not found")
                return pd.DataFrame(columns=['ticker', 'macro_conditioned_signal'])

            df = pd.read_parquet(path)
            if df.empty:
                print("   ⚠️ Macro-conditioned snapshot is empty")
                return pd.DataFrame(columns=['ticker', 'macro_conditioned_signal'])

            if 'ticker' not in df.columns and 'asset_id' in df.columns:
                df = df.rename(columns={'asset_id': 'ticker'})

            score_col = None
            for col in ['signal_composite_regime', 'signal_composite_equal']:
                if col in df.columns:
                    score_col = col
                    break

            if 'ticker' not in df.columns or score_col is None:
                print("   ⚠️ Macro-conditioned snapshot missing required columns")
                return pd.DataFrame(columns=['ticker', 'macro_conditioned_signal'])

            out = df[['ticker', score_col]].copy()
            out = out.rename(columns={score_col: 'macro_conditioned_signal'})
            out['macro_conditioned_signal'] = pd.to_numeric(
                out['macro_conditioned_signal'], errors='coerce'
            )
            out = out.dropna(subset=['ticker', 'macro_conditioned_signal'])
            out['ticker'] = out['ticker'].astype(str)
            out = out.drop_duplicates(subset=['ticker'], keep='last')

            print(f"   ✅ Loaded macro-conditioned snapshot: {len(out)} tickers")
            return out
        except Exception as e:
            print(f"   ⚠️ Could not load macro-conditioned snapshot: {e}")
            return pd.DataFrame(columns=['ticker', 'macro_conditioned_signal'])
    
    def calculate_base_weights(self, universe, score_col, intelligence):
        """Calculate base portfolio weights from scores or strategy blending"""
        
        print("🧬 Calculating base portfolio weights...")
        
        if universe.empty:
            print("   ⚠️ Empty universe, returning empty portfolio")
            return pd.DataFrame()
        
        # Check if we have capital allocations for strategy blending
        allocations = intelligence.get('capital_allocations', {})
        
        if allocations and len(allocations) > 1:
            # Use strategy blending
            return self.construct_blended_portfolio(intelligence, universe)
        else:
            # Use single strategy approach
            return self.construct_single_strategy_portfolio(universe, intelligence, score_col)
    
    def construct_blended_portfolio(self, intelligence, universe):
        """Construct portfolio by blending multiple strategies based on capital allocations"""
        
        print("🧬 Constructing blended portfolio from strategies...")
        
        # Get capital allocations
        allocations = intelligence.get('capital_allocations', {})
        
        if not allocations:
            print("   ⚠️ No capital allocations found, using single strategy")
            return self.construct_single_strategy_portfolio(universe, intelligence)
        
        # Load strategy portfolios
        strategy_portfolios = {}
        strategy_dir = 'data/processed/strategy_portfolios'
        
        for strategy, allocation in allocations.items():
            if allocation > 0.01:  # Only load strategies with >1% allocation
                strategy_file = os.path.join(strategy_dir, f"{strategy}.parquet")
                if os.path.exists(strategy_file):
                    try:
                        df = pd.read_parquet(strategy_file)
                        if not df.empty and 'ticker' in df.columns and 'weight' in df.columns:
                            weights = df.set_index('ticker')['weight']
                            strategy_portfolios[strategy] = weights
                            print(f"   📊 Loaded {strategy}: {len(weights)} positions, {allocation:.1%} allocation")
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy}: {e}")
        
        if not strategy_portfolios:
            print("   ⚠️ No strategy portfolios loaded, falling back to single strategy")
            return self.construct_single_strategy_portfolio(universe, intelligence)
        
        # Blend strategies
        print(f"   🧬 Blending {len(strategy_portfolios)} strategies...")
        
        # Get all tickers from all strategies
        all_tickers = set()
        for weights in strategy_portfolios.values():
            all_tickers.update(weights.index)
        
        # Create blended weights
        blended_weights = pd.Series(0.0, index=list(all_tickers))
        
        for strategy, weights in strategy_portfolios.items():
            allocation = allocations.get(strategy, 0)
            if allocation > 0:
                # Add weighted contribution from this strategy
                aligned_weights = weights.reindex(blended_weights.index).fillna(0)
                blended_weights += allocation * aligned_weights

        # In blended mode the canonical strategy portfolios are already current live
        # selections. Do not collapse them back to the thinner score universe; use
        # score-universe metadata when present and fall back to the reference universe.
        metadata = pd.DataFrame(columns=['ticker', 'Company Name', 'Industry'])
        if isinstance(universe, pd.DataFrame) and not universe.empty and 'ticker' in universe.columns:
            metadata = universe.copy()
            metadata['ticker'] = metadata['ticker'].astype(str).str.strip()
            if 'Company Name' not in metadata.columns:
                metadata['Company Name'] = metadata['ticker']
            else:
                metadata['Company Name'] = (
                    metadata['Company Name'].fillna('').astype(str).str.strip()
                    .where(metadata['Company Name'].fillna('').astype(str).str.strip().ne(''), metadata['ticker'].astype(str))
                )
            if 'Industry' not in metadata.columns:
                metadata['Industry'] = metadata.get('sector', 'Unknown')
            metadata['Industry'] = metadata['Industry'].fillna('Unknown').astype(str)
            metadata = metadata[['ticker', 'Company Name', 'Industry']].drop_duplicates('ticker', keep='first')

        try:
            ref_path = Path('universe/nifty500.csv')
            if ref_path.exists():
                ref = pd.read_csv(ref_path)
                ticker_col = next((c for c in ['Symbol', 'ticker', 'Ticker', 'symbol'] if c in ref.columns), None)
                if ticker_col is not None:
                    ref = ref.copy()
                    ref['ticker'] = ref[ticker_col].astype(str).str.strip().str.upper()
                    ref['ticker'] = ref['ticker'].map(lambda x: x if '.' in x else f"{x}.NS")
                    name_col = next(
                        (c for c in ['Company Name', 'company_name', 'Security Name'] if c in ref.columns),
                        None,
                    )
                    industry_col = next(
                        (c for c in ['Industry', 'industry', 'Sector', 'sector', 'Industry Name'] if c in ref.columns),
                        None,
                    )
                    ref_meta = pd.DataFrame({'ticker': ref['ticker']})
                    ref_meta['Company Name'] = (
                        ref[name_col].fillna('').astype(str)
                        if name_col is not None
                        else ref_meta['ticker']
                    )
                    ref_meta['Industry'] = (
                        ref[industry_col].fillna('Unknown').astype(str)
                        if industry_col is not None
                        else 'Unknown'
                    )
                    metadata = pd.concat([metadata, ref_meta], ignore_index=True)
                    metadata = metadata.drop_duplicates('ticker', keep='first')
        except Exception as exc:
            print(f"   ⚠️ Reference metadata enrichment skipped: {exc}")

        blended_weights = blended_weights[blended_weights > 0.001]  # Remove tiny weights
        
        if blended_weights.sum() > 0:
            blended_weights = blended_weights / blended_weights.sum()
        
        # Convert to portfolio format matching expected structure
        portfolio_data = []
        metadata_lookup = (
            metadata.set_index('ticker')[['Company Name', 'Industry']].to_dict('index')
            if not metadata.empty and 'ticker' in metadata.columns
            else {}
        )
        for ticker, weight in blended_weights.items():
            if weight > 0.001:
                row = {'ticker': ticker, 'Company Name': ticker, 'Industry': 'Unknown'}
                if ticker in metadata_lookup:
                    row.update(metadata_lookup[ticker])
                row['base_weight'] = weight
                portfolio_data.append(row)
        
        portfolio = pd.DataFrame(portfolio_data)
        
        if not portfolio.empty:
            print(f"   ✅ Blended portfolio: {len(portfolio)} positions from {len(strategy_portfolios)} strategies")
            
            # Show strategy contributions
            for strategy, allocation in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
                if allocation > 0.01:
                    print(f"     {strategy}: {allocation:.1%}")
        
        return portfolio
    
    def construct_single_strategy_portfolio(self, universe, intelligence, score_col=None):
        """Construct portfolio using single strategy approach"""
        
        print("📊 Constructing single strategy portfolio...")
        
        # Select top stocks based on regime
        regime = intelligence['regime']
        risk_on_prob = intelligence['risk_on_prob']
        
        # Adjust universe size based on market conditions
        if risk_on_prob > self.risk_on_threshold:
            max_positions = self.max_positions_risk_on
        elif risk_on_prob < self.risk_off_threshold:
            max_positions = self.max_positions_risk_off
        else:
            max_positions = self.max_positions_neutral
        
        # Select top stocks
        top_stocks = universe.head(max_positions).copy()
        
        # Calculate weights using softmax with regime adjustment
        if score_col and score_col in top_stocks.columns:
            scores = top_stocks[score_col].values
            
            # Adjust concentration based on risk-on probability
            concentration_factor = 1.0 + (
                (risk_on_prob - self.concentration_center) * self.concentration_scale
            )
            
            # Apply softmax
            scores_normalized = (scores - scores.mean()) / (scores.std() + 1e-8)
            scores_adjusted = scores_normalized * concentration_factor
            exp_scores = np.exp(scores_adjusted - scores_adjusted.max())
            weights = exp_scores / exp_scores.sum()
        else:
            # Equal weights if no score column
            weights = np.ones(len(top_stocks)) / len(top_stocks)
        
        top_stocks['base_weight'] = weights
        
        print(f"   ✅ Single strategy portfolio: {len(top_stocks)} positions")
        if score_col and score_col in top_stocks.columns:
            concentration_factor = 1.0 + (
                (risk_on_prob - self.concentration_center) * self.concentration_scale
            )
            print(f"   📊 Concentration factor: {concentration_factor:.2f}")
            print(f"   📊 Top position: {weights.max():.2%}")
        
        return top_stocks
    
    def apply_opportunity_enhancement(self, portfolio, opportunity_surface):
        """Enhance weights based on opportunity surface"""

        macro_snapshot = self.load_macro_conditioned_snapshot()

        if opportunity_surface.empty and macro_snapshot.empty:
            portfolio['opportunity_weight'] = portfolio['base_weight']
            return portfolio

        print("🎯 Applying opportunity enhancement...")

        if not opportunity_surface.empty:
            # Merge with opportunity data
            portfolio = portfolio.merge(
                opportunity_surface[['ticker', 'mispricing', 'confirmation']],
                on='ticker',
                how='left'
            )
        else:
            portfolio['mispricing'] = 0.0
            portfolio['confirmation'] = 0.0

        # Fill missing opportunity data
        portfolio['mispricing'] = pd.to_numeric(portfolio['mispricing'], errors='coerce').fillna(0.0)
        portfolio['confirmation'] = pd.to_numeric(portfolio['confirmation'], errors='coerce').fillna(0.0)

        # Legacy opportunity score from opportunity surface
        portfolio['legacy_opportunity_score'] = (
            portfolio['mispricing'] * self.opp_mispricing_weight +
            portfolio['confirmation'] * self.opp_confirmation_weight
        )

        # Merge macro-conditioned signal and convert to cross-sectional rank [0,1]
        if not macro_snapshot.empty:
            portfolio = portfolio.merge(
                macro_snapshot[['ticker', 'macro_conditioned_signal']],
                on='ticker',
                how='left'
            )
            portfolio['macro_conditioned_signal'] = pd.to_numeric(
                portfolio['macro_conditioned_signal'], errors='coerce'
            )
            if portfolio['macro_conditioned_signal'].notna().sum() > 1:
                portfolio['macro_signal_rank'] = portfolio['macro_conditioned_signal'].rank(
                    pct=True, method='average'
                )
            else:
                portfolio['macro_signal_rank'] = self.opp_macro_default_rank
        else:
            portfolio['macro_conditioned_signal'] = np.nan
            portfolio['macro_signal_rank'] = self.opp_macro_default_rank

        # Blend opportunity surface with macro-conditioned state signal
        valuation_signal = (
            pd.to_numeric(portfolio['valuation_signal'], errors='coerce')
            if 'valuation_signal' in portfolio.columns
            else pd.Series(0.50, index=portfolio.index, dtype=float)
        ).fillna(0.50)
        cohesive_rank = (
            pd.to_numeric(portfolio['cohesive_alpha_rank_score'], errors='coerce')
            if 'cohesive_alpha_rank_score' in portfolio.columns
            else pd.Series(0.50, index=portfolio.index, dtype=float)
        ).fillna(0.50)
        total_weight = (
            self.opp_legacy_weight +
            self.opp_macro_weight +
            self.opp_valuation_weight +
            self.opp_cohesive_weight
        )
        portfolio['opportunity_score'] = (
            portfolio['legacy_opportunity_score'] * (self.opp_legacy_weight / total_weight) +
            portfolio['macro_signal_rank'].fillna(self.opp_macro_default_rank) * (self.opp_macro_weight / total_weight) +
            valuation_signal * (self.opp_valuation_weight / total_weight) +
            cohesive_rank * (self.opp_cohesive_weight / total_weight)
        )

        # Apply opportunity multiplier (0.8x to 1.5x)
        opp_multiplier = self.opp_multiplier_base + (portfolio['opportunity_score'] * self.opp_multiplier_span)
        opp_multiplier = np.clip(
            opp_multiplier,
            self.opp_multiplier_min,
            self.opp_multiplier_max,
        )
        
        portfolio['opportunity_weight'] = portfolio['base_weight'] * opp_multiplier
        
        # Renormalize
        total_weight = portfolio['opportunity_weight'].sum()
        if total_weight > 0:
            portfolio['opportunity_weight'] = portfolio['opportunity_weight'] / total_weight
        
        enhanced_positions = (opp_multiplier > 1.1).sum()
        print(f"   ✅ Enhanced {enhanced_positions} positions based on opportunities")
        macro_cov = int(portfolio['macro_conditioned_signal'].notna().sum())
        print(f"   🧠 Macro-conditioned coverage: {macro_cov}/{len(portfolio)}")
        
        return portfolio
    
    def apply_risk_controls(self, portfolio, intelligence):
        """Apply all risk controls and constraints"""
        
        print("🛡️ Applying risk controls...")
        
        if portfolio.empty:
            return portfolio
        
        # Start with opportunity weights
        portfolio['risk_controlled_weight'] = portfolio['opportunity_weight'].copy()

        max_single = self.constraints['max_single_position']
        max_sector = self.constraints['max_sector_exposure']
        pre_cap_over_limit = int((portfolio['risk_controlled_weight'] > max_single).sum())
        pre_cap_sector_totals = portfolio.groupby('Industry')['risk_controlled_weight'].sum()
        pre_cap_over_sectors = int((pre_cap_sector_totals > max_sector).sum())

        # 1-3. Cap single-position and sector concentration, then redistribute
        # toward full deployment (target_sum=1.0) using headroom only -- never
        # by uniformly rescaling everyone back up, which would push already
        # -capped positions/sectors back over their limit. See
        # _cap_aware_rescale for why a naive rescale-to-1.0 is unsafe here.
        portfolio['risk_controlled_weight'] = _cap_aware_rescale(
            portfolio['risk_controlled_weight'],
            target_sum=1.0,
            position_cap=max_single,
            group_ids=portfolio['Industry'],
            group_cap=max_sector,
        )

        if pre_cap_over_limit:
            print(f"   📊 Capped {pre_cap_over_limit} positions at {max_single:.1%}")
        if pre_cap_over_sectors:
            print(f"   📊 Applied sector caps to {pre_cap_over_sectors} sectors")

        achieved_sum = portfolio['risk_controlled_weight'].sum()
        if achieved_sum < 0.999:
            print(
                f"   ⚠️ Concentration caps binding: only {achieved_sum:.1%} of the "
                f"book could be deployed within max_single_position/max_sector_exposure "
                f"limits (need more eligible positions to reach full deployment)."
            )

        # 4. Turnover governance relative to previous canonical weights.
        try:
            prev = self.state_manager.read_portfolio_weights()
            if not prev.empty:
                tick_col = 'ticker' if 'ticker' in prev.columns else ('symbol' if 'symbol' in prev.columns else None)
                w_col = 'weight' if 'weight' in prev.columns else ('final_weight' if 'final_weight' in prev.columns else None)
                if tick_col and w_col:
                    prev_df = prev[[tick_col, w_col]].copy()
                    prev_df[tick_col] = prev_df[tick_col].astype(str).str.strip()
                    prev_df[w_col] = pd.to_numeric(prev_df[w_col], errors='coerce').fillna(0.0)
                    prev_map = dict(zip(prev_df[tick_col], prev_df[w_col]))

                    cur_map = {
                        str(t): float(w)
                        for t, w in zip(
                            portfolio['ticker'].astype(str).tolist(),
                            pd.to_numeric(portfolio['risk_controlled_weight'], errors='coerce').fillna(0.0).tolist(),
                        )
                    }
                    keys = sorted(set(prev_map.keys()) | set(cur_map.keys()))
                    prev_vec = np.array([float(prev_map.get(k, 0.0)) for k in keys], dtype=float)
                    cur_vec = np.array([float(cur_map.get(k, 0.0)) for k in keys], dtype=float)
                    turnover = 0.5 * float(np.abs(cur_vec - prev_vec).sum())
                    max_turnover = float(
                        self.constraints.get('max_turnover', self._as_float(None, 0.25))
                    )
                    if turnover > max_turnover and turnover > 1e-12:
                        blend = max_turnover / turnover
                        adj_vec = prev_vec + blend * (cur_vec - prev_vec)
                        adj_vec = np.clip(adj_vec, 0.0, None)
                        ssum = float(adj_vec.sum())
                        if ssum > 1e-12:
                            adj_vec = adj_vec / ssum
                            adj_map = {k: float(v) for k, v in zip(keys, adj_vec)}
                            portfolio['risk_controlled_weight'] = portfolio['ticker'].astype(str).map(
                                lambda t: adj_map.get(t, 0.0)
                            ).astype(float)
                            print(
                                f"   📉 Turnover bounded: {turnover:.1%} -> {max_turnover:.1%}"
                            )
        except Exception as e:
            print(f"   ⚠️ Turnover governance skipped: {e}")
        
        return portfolio
    
    def apply_regime_overlay(self, portfolio, intelligence):
        """Apply regime-based portfolio overlay with dual engine coordination"""
        
        print("🌍 Applying regime overlay with dual engine coordination...")
        
        if portfolio.empty:
            return portfolio

        # Single-regime-authority default: keep canonical intelligent state in charge.
        if not self.use_dual_engine_override:
            print("   🧭 Regime authority = intelligent_market_state (dual engine is advisory)")
            return self.apply_traditional_regime_overlay(portfolio, intelligence)
        
        # Get engine allocation results
        engine_allocation = intelligence.get('engine_allocation')
        if engine_allocation is None:
            # Fallback to traditional approach
            return self.apply_traditional_regime_overlay(portfolio, intelligence)
        
        regime = engine_allocation.regime.value.lower()
        final_exposure = engine_allocation.total_allocation
        crisis_active = intelligence.get('crisis_engine_active', False)
        trend_active = intelligence.get('trend_engine_active', False)
        
        print(f"   🎯 Dual Engine Results:")
        print(f"      Regime: {engine_allocation.regime.value}")
        print(f"      Active Engine: {engine_allocation.active_engine}")
        print(f"      Final Exposure: {final_exposure:.1%}")
        
        # Apply engine-specific portfolio adjustments
        if crisis_active:
            # Crisis engine is active - apply crisis-specific adjustments
            portfolio = self.apply_crisis_engine_overlay(portfolio, engine_allocation, intelligence)
        elif trend_active:
            # Trend engine is active - apply trend-specific adjustments
            portfolio = self.apply_trend_engine_overlay(portfolio, engine_allocation, intelligence)
        else:
            # No engine active - minimal exposure
            print("   💤 No engine active - minimal exposure mode")
            portfolio['final_weight'] = portfolio['risk_controlled_weight'] * 0.1  # 10% minimal exposure
        
        # Ensure final exposure matches engine allocation, without pushing any
        # position/sector back over its (exposure-scaled) cap -- see
        # _cap_aware_rescale.
        portfolio['final_weight'] = _cap_aware_rescale(
            portfolio['final_weight'],
            target_sum=final_exposure,
            position_cap=self.constraints['max_single_position'] * final_exposure,
            group_ids=portfolio['Industry'],
            group_cap=self.constraints['max_sector_exposure'] * final_exposure,
        )

        print(f"   ✅ Applied {regime} regime overlay with {engine_allocation.active_engine} engine")
        print(f"   📊 Target exposure: {final_exposure:.1%}")
        
        return portfolio
    
    def apply_crisis_engine_overlay(self, portfolio, engine_allocation, intelligence):
        """Apply crisis engine specific portfolio adjustments"""
        
        print("   🔥 Applying Crisis Engine overlay...")
        
        crisis_allocation = engine_allocation.crisis_allocation
        regime = engine_allocation.regime
        
        # Crisis engine portfolio characteristics:
        # 1. Favor volatility convexity positions
        # 2. Reduce correlation to traditional risk assets
        # 3. Focus on tail risk protection
        # 4. Accept bleeding during normal periods
        
        # Start with crisis allocation
        portfolio['final_weight'] = portfolio['risk_controlled_weight'] * crisis_allocation
        
        # Crisis-specific sector adjustments
        if regime == MarketRegime.PANIC:
            # Maximum crisis mode - extreme defensive positioning
            defensive_sectors = ['Utilities', 'Consumer Staples', 'Healthcare', 'Real Estate']
            avoid_sectors = ['Technology', 'Consumer Discretionary', 'Energy']
            
            # Boost defensive sectors
            for sector in defensive_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= 1.5
            
            # Reduce cyclical exposure
            for sector in avoid_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= 0.5
                    
            print("   💀 PANIC mode - Maximum defensive positioning")
            
        elif regime == MarketRegime.HOSTILE:
            # Crisis mode - moderate defensive positioning
            defensive_sectors = ['Utilities', 'Consumer Staples', 'Healthcare']
            
            # Moderate boost to defensive sectors
            for sector in defensive_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= 1.2
                    
            print("   ⚠️ HOSTILE mode - Defensive positioning")
        
        # Crisis engine expects to bleed - this is normal behavior
        print("   🩸 Crisis engine active - expect small bleeding during normal periods")
        print("   💎 Positioned for volatility convexity capture")
        
        return portfolio
    
    def apply_trend_engine_overlay(self, portfolio, engine_allocation, intelligence):
        """Apply trend engine specific portfolio adjustments"""
        
        print("   📈 Applying Trend Engine overlay...")
        
        trend_allocation = engine_allocation.trend_allocation
        regime = engine_allocation.regime
        strategy_performance = intelligence.get('strategy_performance', {})
        
        # Trend engine portfolio characteristics:
        # 1. Follow momentum and trend signals
        # 2. Favor growth and cyclical sectors in supportive regimes
        # 3. Reduce exposure in hostile regimes
        # 4. Adapt based on strategy performance
        
        # Start with trend allocation
        portfolio['final_weight'] = portfolio['risk_controlled_weight'] * trend_allocation
        
        # Regime-specific trend adjustments
        if regime == MarketRegime.SUPPORTIVE:
            # Full trend following mode
            growth_sectors = ['Technology', 'Industrials', 'Materials', 'Consumer Discretionary']
            
            # Boost growth sectors
            for sector in growth_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= 1.3
                    
            print("   🚀 SUPPORTIVE mode - Full trend following")
            
        elif regime == MarketRegime.NEUTRAL:
            # Balanced trend following
            balanced_boost = 1.1
            portfolio['final_weight'] *= balanced_boost
            
            print("   ⚖️ NEUTRAL mode - Balanced trend following")
            
        elif regime == MarketRegime.HOSTILE:
            # Defensive trend following - reduced exposure
            defensive_trend = 0.7
            portfolio['final_weight'] *= defensive_trend
            
            print("   🛡️ HOSTILE mode - Defensive trend following")
        
        # Strategy performance adjustments
        if strategy_performance:
            # Check momentum strategy performance
            mom_strategies = ['mom_6m', 'mom_12m', 'dual_momentum']
            avg_mom_sharpe = np.mean([strategy_performance.get(s, {}).get('sharpe', 0) for s in mom_strategies])
            
            if avg_mom_sharpe > 0.8:
                print("   📊 Momentum strategies performing well - trend boost")
                portfolio['final_weight'] *= 1.1
            elif avg_mom_sharpe < 0.2:
                print("   📊 Momentum strategies underperforming - trend reduction")
                portfolio['final_weight'] *= 0.9
        
        return portfolio
    
    def apply_traditional_regime_overlay(self, portfolio, intelligence):
        """Canonical intelligent-state regime overlay."""
        
        print("   🧭 Applying canonical regime overlay...")
        
        regime = intelligence['regime']
        allowed_exposure = intelligence['allowed_exposure']
        risk_on_prob = intelligence['risk_on_prob']
        strategy_performance = intelligence.get('strategy_performance', {})
        
        # Calculate risk-scaled exposure based on portfolio volatility
        estimated_portfolio_vol = self.estimated_portfolio_vol
        target_vol = self.target_portfolio_vol
        
        risk_scaled_result = self.exposure_calculator.calculate_risk_scaled_exposure(
            portfolio_volatility=estimated_portfolio_vol,
            target_volatility=target_vol
        )
        
        # Combine exposures: take the minimum (most conservative)
        combined_exposure = self.exposure_calculator.combine_exposures(
            allowed_exposure=allowed_exposure,
            risk_scaled_exposure=risk_scaled_result.value
        )
        
        # Use the combined (minimum) exposure
        final_exposure = combined_exposure.value

        # Freeze-state hard clamp for capital preservation.
        freeze_state = intelligence.get('freeze_state', {}) or {}
        if bool(freeze_state.get('freeze_active', False)):
            freeze_cap = self._as_float(
                (freeze_state.get('actions') or {}).get('target_max_exposure'),
                self.default_freeze_exposure_cap,
            )
            if final_exposure > freeze_cap:
                print(f"   🧊 Freeze exposure clamp: {final_exposure:.1%} -> {freeze_cap:.1%}")
            final_exposure = min(final_exposure, freeze_cap)
        
        # Apply exposure scaling
        portfolio['final_weight'] = portfolio['risk_controlled_weight'] * final_exposure
        
        # Apply regime-specific adjustments
        if regime in ['crisis', 'slowdown', 'hostile', 'panic']:
            # Favor quality and defensives
            quality_boost = self.crisis_quality_boost
            defensive_sectors = ['Utilities', 'Consumer Staples', 'Healthcare']
            
            for sector in defensive_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= quality_boost
        
        elif regime in ['boom', 'expansion', 'supportive']:
            # Favor growth and cyclicals
            growth_boost = self.expansion_growth_boost
            cyclical_sectors = ['Technology', 'Industrials', 'Materials']
            
            for sector in cyclical_sectors:
                sector_mask = portfolio['Industry'] == sector
                if sector_mask.any():
                    portfolio.loc[sector_mask, 'final_weight'] *= growth_boost
        
        # Renormalize to maintain target exposure, without pushing any
        # position/sector back over its (exposure-scaled) cap -- see
        # _cap_aware_rescale. risk_controlled_weight already respects
        # max_single_position/max_sector_exposure (apply_risk_controls), but
        # the regime quality/growth boosts just above can reintroduce a
        # violation, so caps are re-applied here too.
        portfolio['final_weight'] = _cap_aware_rescale(
            portfolio['final_weight'],
            target_sum=final_exposure,
            position_cap=self.constraints['max_single_position'] * final_exposure,
            group_ids=portfolio['Industry'],
            group_cap=self.constraints['max_sector_exposure'] * final_exposure,
        )

        print(f"   ✅ Applied {regime} regime overlay with strategy intelligence")
        print(f"   📊 Target exposure: {final_exposure:.1%}")
        
        # Show performance-based adjustments made
        if strategy_performance:
            performing_strategies = [s for s, p in strategy_performance.items() 
                                   if p.get('sharpe', 0) > 0.5]
            if performing_strategies:
                print(f"   📈 Well-performing strategies: {', '.join(performing_strategies[:3])}")
        
        return portfolio
    
    def assign_position_roles(self, portfolio):
        """Assign roles to portfolio positions"""
        
        print("🎭 Assigning position roles...")
        
        if portfolio.empty:
            return portfolio
        
        # Assign roles based on weight and characteristics
        portfolio['position_role'] = 'Satellite'  # Default
        
        # Core positions (top 40% by weight)
        top_40_threshold = portfolio['final_weight'].quantile(0.6)
        portfolio.loc[portfolio['final_weight'] >= top_40_threshold, 'position_role'] = 'Core'
        
        # Quality positions (defensive sectors)
        defensive_sectors = ['Utilities', 'Consumer Staples', 'Healthcare']
        quality_mask = portfolio['Industry'].isin(defensive_sectors)
        portfolio.loc[quality_mask, 'position_role'] = 'Quality'
        
        # Value positions (if we have value indicators)
        # This would be enhanced with actual value metrics
        
        role_counts = portfolio['position_role'].value_counts()
        print(f"   ✅ Roles assigned: {dict(role_counts)}")
        
        return portfolio
    
    def calculate_portfolio_analytics(self, portfolio, intelligence):
        """Calculate comprehensive portfolio analytics"""
        
        print("📈 Calculating portfolio analytics...")
        
        analytics = {
            'timestamp': datetime.now().isoformat(),
            'portfolio_summary': {},
            'risk_metrics': {},
            'sector_allocation': {},
            'position_analysis': {},
            'compliance_check': {},
            'intelligence_integration': {}
        }
        
        if portfolio.empty:
            analytics['portfolio_summary'] = {
                'total_positions': 0,
                'total_exposure': 0.0,
                'cash_level': 1.0,
                'largest_position': 0.0
            }
            return analytics
        
        # Portfolio summary
        total_exposure = portfolio['final_weight'].sum()
        analytics['portfolio_summary'] = {
            'total_positions': len(portfolio),
            'total_exposure': float(total_exposure),
            'cash_level': float(1.0 - total_exposure),
            'largest_position': float(portfolio['final_weight'].max()),
            'smallest_position': float(portfolio['final_weight'].min()),
            'median_position': float(portfolio['final_weight'].median()),
            'concentration_ratio': float(portfolio['final_weight'].head(5).sum())  # Top 5 concentration
        }
        
        # Risk metrics
        analytics['risk_metrics'] = {
            'diversification_score': min(1.0, len(portfolio) / 20),  # 20+ positions = full diversification
            'concentration_risk': float(portfolio['final_weight'].max()),
            'sector_concentration': float(portfolio.groupby('Industry')['final_weight'].sum().max()),
            'position_count': len(portfolio),
            'effective_positions': float(1 / (portfolio['final_weight'] ** 2).sum())  # Herfindahl index
        }
        
        # Sector allocation
        sector_allocation = portfolio.groupby('Industry')['final_weight'].sum().to_dict()
        analytics['sector_allocation'] = {k: float(v) for k, v in sector_allocation.items()}
        
        # Position analysis
        analytics['position_analysis'] = {
            'top_positions': portfolio.nlargest(10, 'final_weight')[['ticker', 'Company Name', 'final_weight', 'position_role']].to_dict('records'),
            'role_distribution': portfolio['position_role'].value_counts().to_dict()
        }
        
        # Compliance check
        compliance = {
            'max_single_position': portfolio['final_weight'].max() <= self.constraints['max_single_position'],
            'max_sector_exposure': portfolio.groupby('Industry')['final_weight'].sum().max() <= self.constraints['max_sector_exposure'],
            'min_diversification': len(portfolio) >= self.constraints['min_diversification'],
            'total_exposure_limit': total_exposure <= self.constraints['max_total_exposure']
        }
        analytics['compliance_check'] = compliance
        analytics['compliance_check']['all_compliant'] = all(compliance.values())
        
        # Intelligence integration with dual engine diagnostics
        engine_allocation = intelligence.get('engine_allocation')
        
        analytics['intelligence_integration'] = {
            'regime': intelligence['regime'],
            'allowed_exposure': intelligence['allowed_exposure'],
            'legacy_allowed_exposure': intelligence.get('legacy_allowed_exposure'),
            'governor_deployment_floor': float(intelligence.get('governor_deployment_floor', 0.0) or 0.0),
            'capital_allocator_exposure': float(sum((intelligence.get('capital_allocations') or {}).values())),
            'capital_allocator_exposure_cap': float(intelligence.get('capital_allocator_effective_exposure_cap') or 0.0),
            'risk_on_probability': intelligence['risk_on_prob'],
            'ai_active': intelligence['ai_active'],
            'freeze_active': bool(intelligence.get('freeze_active', False)),
            'regime_authority': intelligence.get('regime_authority', 'unknown'),
            'regime_alignment': intelligence.get('regime_alignment', 'unknown'),
            'capital_structure_regime': intelligence.get('capital_structure_regime', 'UNKNOWN'),
            'equity_budget_inr': float(intelligence.get('equity_budget_inr', 0.0) or 0.0),
            'options_budget_inr': float(intelligence.get('options_budget_inr', 0.0) or 0.0),
            'cash_reserve_inr': float(intelligence.get('cash_reserve_inr', 0.0) or 0.0),
            'governor_primary_rationale': intelligence.get('governor_primary_rationale', ''),
            'market_state_compliance': abs(total_exposure - intelligence['allowed_exposure']) < 0.05
        }
        
        # Add dual engine diagnostics if available
        if engine_allocation:
            analytics['dual_engine_coordination'] = {
                'active_engine': engine_allocation.active_engine,
                'market_regime': engine_allocation.regime.value,
                'regime_confidence': engine_allocation.regime_confidence,
                'trend_allocation': engine_allocation.trend_allocation,
                'crisis_allocation': engine_allocation.crisis_allocation,
                'total_engine_allocation': engine_allocation.total_allocation,
                'crisis_engine_active': intelligence.get('crisis_engine_active', False),
                'trend_engine_active': intelligence.get('trend_engine_active', False)
            }
            
            # Get coordination diagnostics
            coordination_diagnostics = self.dual_engine_coordinator.get_coordination_diagnostics()
            analytics['engine_diagnostics'] = coordination_diagnostics
            
            # Validate institutional discipline
            discipline_check = self.dual_engine_coordinator.validate_institutional_discipline()
            analytics['institutional_discipline'] = discipline_check
        else:
            analytics['dual_engine_coordination'] = {
                'status': 'Dual engine coordination not available'
            }
        
        print(f"   ✅ Analytics calculated")
        print(f"   📊 Total exposure: {total_exposure:.1%}")
        print(f"   📊 Positions: {len(portfolio)}")
        print(f"   📊 Compliance: {'✅' if analytics['compliance_check']['all_compliant'] else '❌'}")
        
        return analytics
    
    def save_portfolio(self, portfolio, analytics):
        """Save final portfolio and analytics"""
        
        print("💾 Saving portfolio...")
        skip_portfolio_write = False
        
        # Save portfolio weights
        if not portfolio.empty:
            # Prepare output columns
            output_cols = [
                'ticker', 'Company Name', 'Industry', 'final_weight', 
                'position_role', 'base_weight', 'opportunity_weight',
                'selection_score', 'cohesive_alpha_score', 'margin_of_safety_pct',
                'owner_earnings_yield_v2', 'valuation_signal'
            ]
            output_cols = [c for c in output_cols if c in portfolio.columns]
            
            portfolio_output = portfolio[output_cols].copy()
            # Canonical columns for StateFileManager validation
            portfolio_output["date"] = pd.to_datetime(datetime.now().date())
            portfolio_output["symbol"] = portfolio_output.get("ticker", "").astype(str)
            portfolio_output["weight"] = pd.to_numeric(
                portfolio_output.get("final_weight", 0.0), errors="coerce"
            ).fillna(0.0)
            portfolio_output["exposure"] = portfolio_output["weight"]

            # Guardrail: avoid overwriting a valid live portfolio with an all-zero
            # integration snapshot (can happen when engines are dormant).
            try:
                effective_exposure = float(portfolio_output["weight"].sum())
                if effective_exposure <= 1e-8:
                    existing = self.state_manager.read_portfolio_weights()
                    if not existing.empty and "weight" in existing.columns:
                        ew = pd.to_numeric(existing["weight"], errors="coerce").fillna(0.0)
                        if int((ew > 0).sum()) >= 5 and float(ew.sum()) > 0.01:
                            skip_portfolio_write = True
                            print(
                                "   ⚠️ Generated portfolio has ~0 exposure; "
                                "preserving existing canonical portfolio_weights.parquet"
                            )
            except Exception:
                logger.exception("Failed during zero-exposure guardrail evaluation")
                raise

            if not skip_portfolio_write:
                try:
                    self.state_manager.write_portfolio_weights(portfolio_output)
                    print(f"   ✅ Portfolio saved (canonical): {self.paths['output']}")
                except Exception as e:
                    print(f"   ⚠️ Canonical write failed, falling back to direct write: {e}")
                    os.makedirs(os.path.dirname(self.paths['output']), exist_ok=True)
                    portfolio_output.to_parquet(self.paths['output'], index=False)
        else:
            # Save empty portfolio
            empty_portfolio = pd.DataFrame(
                columns=["date", "symbol", "weight", "exposure", "ticker", "final_weight"]
            )
            preserve_existing = False
            try:
                existing = self.state_manager.read_portfolio_weights()
                if not existing.empty and "weight" in existing.columns:
                    ew = pd.to_numeric(existing["weight"], errors="coerce").fillna(0.0)
                    preserve_existing = int((ew > 0).sum()) >= 5 and float(ew.sum()) > 0.01
            except Exception:
                logger.exception("Failed evaluating existing portfolio preservation condition")
                raise

            if preserve_existing:
                print("   ⚠️ Empty portfolio generated; preserving existing canonical portfolio weights")
            else:
                try:
                    self.state_manager.write_portfolio_weights(empty_portfolio)
                    print(f"   ✅ Empty portfolio saved (canonical): {self.paths['output']}")
                except Exception as e:
                    print(f"   ⚠️ Canonical write failed, falling back to direct write: {e}")
                    os.makedirs(os.path.dirname(self.paths['output']), exist_ok=True)
                    empty_portfolio.to_parquet(self.paths['output'], index=False)
        
        # Save analytics
        try:
            self.state_manager.write_portfolio_analytics(analytics)
            print(f"   ✅ Analytics saved (canonical): {self.paths['analytics']}")
        except Exception as e:
            print(f"   ⚠️ Canonical analytics write failed, falling back: {e}")
            with open(self.paths['analytics'], 'w') as f:
                json.dump(analytics, f, indent=2, default=str)
            print(f"   ✅ Analytics saved: {self.paths['analytics']}")
    
    def run_portfolio_construction(self):
        """Main portfolio construction process"""
        
        print("🎯 PORTFOLIO GOVERNOR - NORTHSTAR V3")
        print("=" * 60)
        
        # Step 1: Load market intelligence
        intelligence = self.load_market_intelligence()
        
        # Step 2: Load stock universe
        universe, score_col = self.load_universe_scores()
        
        # Step 3: Load opportunity surface
        opportunity_surface = self.load_opportunity_surface()
        
        # Step 4: Calculate base weights
        portfolio = self.calculate_base_weights(universe, score_col, intelligence)
        
        if portfolio.empty:
            print("⚠️ No valid portfolio generated - saving empty portfolio")
            analytics = self.calculate_portfolio_analytics(portfolio, intelligence)
            self.save_portfolio(portfolio, analytics)
            return portfolio, analytics
        
        # Step 5: Apply opportunity enhancement
        portfolio = self.apply_opportunity_enhancement(portfolio, opportunity_surface)
        
        # Step 6: Apply risk controls
        portfolio = self.apply_risk_controls(portfolio, intelligence)
        
        # Step 7: Apply regime overlay
        portfolio = self.apply_regime_overlay(portfolio, intelligence)
        
        # Step 8: Assign position roles
        portfolio = self.assign_position_roles(portfolio)
        
        # Step 9: Calculate analytics
        analytics = self.calculate_portfolio_analytics(portfolio, intelligence)
        
        # Step 10: Save portfolio
        self.save_portfolio(portfolio, analytics)
        
        print("\n✅ PORTFOLIO CONSTRUCTION COMPLETE")
        print(f"📊 Final Portfolio: {len(portfolio)} positions, {analytics['portfolio_summary']['total_exposure']:.1%} exposure")
        
        return portfolio, analytics

def main():
    """Main execution function"""
    
    governor = PortfolioGovernor()
    portfolio, analytics = governor.run_portfolio_construction()
    
    return portfolio, analytics

if __name__ == "__main__":
    main()
