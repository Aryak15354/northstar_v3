"""
PortfolioGovernor — The top-level capital structure authority for Northstar V3.

The Governor runs once per morning, before any allocation decisions are made.
It produces a CapitalStructure that governs the entire day's deployment.

The Governor's decision process:
1. Read all regime signals from UnifiedState
2. Read crisis probability from crisis_engine
3. Read current drawdown and NAV from PnLState (Gap 5)
4. Look up the base capital structure from the RegimeCapitalTable
5. Apply modifiers (drawdown, recovery, crisis, NAV size)
6. Enforce hard limits
7. Validate the resulting structure sums to 1.0
8. Write the decision to allocation_history.parquet
9. Inject the budget into ConvexAllocator and capital_policy.py
10. Emit CAPITAL_STRUCTURE_SET event on the event bus
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple, List
import pandas as pd
import yaml

from .capital_structure import CapitalStructure, CapitalStructureRegime, RegimeCapitalTable
from .governor_state import GovernorState

logger = logging.getLogger(__name__)


class PortfolioGovernor:
    """The single authority for top-level capital structure decisions."""

    DEFAULT_CONFIG_PATH = Path("config/portfolio_governor_config.yaml")

    def __init__(self, config: Optional[dict] = None, crisis_engine=None, event_bus=None, data_dir: Optional[str] = None):
        """
        Initialize the Portfolio Governor.
        
        Args:
            config: Full system config (reads portfolio_governor section)
            crisis_engine: Reference to crisis_engine.py instance
            event_bus: For emitting governance events
        """
        self.config = self._resolve_config(config)
        self.crisis_engine = crisis_engine
        self.event_bus = event_bus
        self.data_dir = Path(data_dir) if data_dir else Path('data')
        self.starting_capital_inr = self.config.get('starting_capital_inr', 10_000_000)
        self.current_structure: Optional[CapitalStructure] = None
        self.last_caution_score: float = 0.0
        
        # Load governor config
        gov_config = self.config.get('portfolio_governor', {})
        if not isinstance(gov_config, dict) or not isinstance(gov_config.get('regime_table'), dict):
            raise ValueError(
                "PortfolioGovernor requires portfolio_governor.regime_table config. "
                f"Expected config from {self.DEFAULT_CONFIG_PATH}."
            )

        self.default_structure = dict(
            gov_config.get(
                'default_capital_structure',
                gov_config['regime_table'].get(CapitalStructureRegime.STANDARD.value, {}),
            )
        )
        self.regime_table = {
            str(regime_name): dict(values or {})
            for regime_name, values in dict(gov_config.get('regime_table', {})).items()
        }
        self.modifiers = gov_config.get('modifiers', {})
        self.hard_limits = gov_config.get('hard_limits', RegimeCapitalTable.HARD_LIMITS)
        
        # Persistent state file
        self.state_file = self.data_dir / 'portfolio' / 'governor_state.json'
        self.allocation_history_file = self.data_dir / 'intelligence' / 'allocation_history.parquet'
        
        # Load persistent state
        self.persistent_state = self._load_persistent_state()
        
        logger.info("PortfolioGovernor initialized")

    @classmethod
    def _resolve_config(cls, config: Optional[dict]) -> dict:
        resolved = dict(config or {})
        if isinstance(resolved.get('portfolio_governor'), dict) and resolved.get('portfolio_governor', {}).get('regime_table'):
            return resolved

        config_path = cls.DEFAULT_CONFIG_PATH
        if not config_path.exists():
            raise ValueError(
                "PortfolioGovernor config missing and default config file was not found at "
                f"{config_path}."
            )

        payload = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid governor config payload at {config_path}")

        resolved.setdefault('portfolio_governor', payload)
        resolved.setdefault('starting_capital_inr', payload.get('starting_capital_inr', 10_000_000))
        return resolved

    @staticmethod
    def _iter_open_option_positions(payload: object) -> List[dict]:
        if isinstance(payload, dict):
            positions = payload.get("open_positions", {})
            if isinstance(positions, dict):
                return [dict(pos or {}) for pos in positions.values()]
            if isinstance(positions, list):
                return [dict(pos or {}) for pos in positions]
        return []

    @staticmethod
    def _position_notional(position: dict) -> float:
        for key in ("notional", "max_loss", "current_value", "entry_credit_debit"):
            value = pd.to_numeric(position.get(key), errors="coerce")
            if pd.notna(value):
                return float(abs(value))
        return 0.0

    def _get_options_notional_deployed(self) -> float:
        path = self.data_dir / "options" / "live" / "options_runtime_state.json"
        if not path.exists():
            return 0.0
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            positions = self._iter_open_option_positions(payload)
            return float(sum(self._position_notional(position) for position in positions))
        except Exception as exc:
            logger.warning("Could not read options notional from %s: %s", path, exc)
            return 0.0

    def _load_persistent_state(self) -> dict:
        """Load persistent governor state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load governor state: {e}")
        
        # Default state
        return {
            'last_decision_date': None,
            'last_decision_regime': 'STANDARD',
            'days_in_current_regime': 0,
            'recovery_days_elapsed': 0,
            'drawdown_at_last_decision': 0.0,
            'regime_history': [],
        }

    def _save_persistent_state(self) -> None:
        """Save persistent governor state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.persistent_state, f, indent=2)

    def compute_capital_structure(self, unified_state) -> Optional[CapitalStructure]:
        """
        Compute the capital structure for today.
        
        This is pure computation — no side effects. Returns a CapitalStructure.
        """
        if getattr(unified_state, "_state_is_stale", False):
            age = getattr(unified_state, "_state_age_hours", None)
            logger.error(
                "Governor refusing to compute capital structure on state that is %s hours old. "
                "Run sync_canonical_state.py first.",
                f"{float(age):.1f}" if isinstance(age, (int, float)) else "unknown",
            )
            return None

        # Extract regime inputs (using actual UnifiedState structure)
        market_regime = unified_state.market.regime
        volatility_regime = unified_state.market.volatility_regime
        macro_regime = unified_state.macro.regime if hasattr(unified_state.macro, 'regime') else 'NEUTRAL'
        sentiment_regime = unified_state.sentiment.market_sentiment_regime.value if hasattr(unified_state.sentiment.market_sentiment_regime, 'value') else str(unified_state.sentiment.market_sentiment_regime)
        econ_activity_regime = unified_state.alternative_data.economic_activity_regime.value if hasattr(unified_state.alternative_data.economic_activity_regime, 'value') else str(unified_state.alternative_data.economic_activity_regime)
        crisis_probability = self._get_crisis_probability()
        current_drawdown = unified_state.pnl_state.current_drawdown_pct
        current_nav = unified_state.pnl_state.current_nav_inr
        coherence_score = float(getattr(unified_state.market, 'coherence_score', 1.0) or 1.0)
        
        # Compute caution score
        caution_score = self._compute_caution_score(
            market_regime, volatility_regime, macro_regime,
            sentiment_regime, econ_activity_regime, crisis_probability,
            coherence_score=coherence_score,
        )
        self.last_caution_score = caution_score
        
        # Map to regime
        base_regime = self._caution_score_to_regime(caution_score)
        
        # Look up base fractions
        base_fractions = self._get_base_fractions(base_regime)
        
        equity_frac = base_fractions['equity_fraction']
        options_frac = base_fractions['options_fraction']
        cash_frac = base_fractions['cash_fraction']
        
        modifiers_applied = []
        
        # Apply drawdown modifier
        equity_frac, cash_frac, applied = self._apply_drawdown_modifier(
            equity_frac, cash_frac, current_drawdown
        )
        modifiers_applied.extend(applied)
        
        # Apply recovery modifier
        equity_frac, cash_frac, applied = self._apply_recovery_modifier(
            equity_frac, cash_frac, current_drawdown
        )
        modifiers_applied.extend(applied)
        
        # Apply crisis override
        equity_frac, options_frac, cash_frac, base_regime, applied = self._apply_crisis_override(
            equity_frac, options_frac, cash_frac, base_regime, crisis_probability
        )
        modifiers_applied.extend(applied)
        
        # Apply NAV size protection
        equity_frac, cash_frac, applied = self._apply_nav_size_protection(
            equity_frac, cash_frac, current_nav
        )
        modifiers_applied.extend(applied)
        
        # Enforce hard limits
        equity_frac, options_frac, cash_frac = self._enforce_hard_limits(
            equity_frac, options_frac, cash_frac
        )
        
        # Re-normalize to exactly 1.0
        total = equity_frac + options_frac + cash_frac
        equity_frac /= total
        options_frac /= total
        cash_frac /= total
        
        # Compute INR amounts
        total_capital = current_nav if current_nav > 0 else self.starting_capital_inr
        options_deployed = self._get_options_notional_deployed()
        equity_budget_inr = max((equity_frac * total_capital) - options_deployed, 0.0)

        # Build rationale
        primary_rationale = self._build_rationale(base_regime, caution_score, modifiers_applied)
        
        # Compute confidence
        confidence = self._compute_governance_confidence(
            caution_score,
            modifiers_applied,
            coherence_score=coherence_score,
        )
        
        # Create structure
        today = datetime.now()
        today_market_close = today.replace(hour=15, minute=30, second=0, microsecond=0)
        
        structure = CapitalStructure(
            equity_fraction=equity_frac,
            options_fraction=options_frac,
            cash_fraction=cash_frac,
            total_capital_inr=total_capital,
            equity_budget_inr=equity_budget_inr,
            options_budget_inr=options_frac * total_capital,
            cash_reserve_inr=cash_frac * total_capital,
            capital_structure_regime=base_regime,
            confidence=confidence,
            market_regime=market_regime,
            volatility_regime=volatility_regime,
            macro_regime=macro_regime,
            sentiment_regime=sentiment_regime,
            economic_activity_regime=econ_activity_regime,
            crisis_probability=crisis_probability,
            current_drawdown_pct=current_drawdown,
            current_nav_inr=current_nav,
            primary_rationale=primary_rationale,
            modifiers_applied=modifiers_applied,
            overrides_active=[],
            valid_for_date=today,
            expires_at=today_market_close,
            computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        
        structure.validate()
        return structure

    def _extract_macro_regime(self, unified_state) -> str:
        """Extract macro regime from UnifiedState."""
        try:
            return unified_state.macro.regime if hasattr(unified_state.macro, 'regime') else 'NEUTRAL'
        except Exception:
            return 'NEUTRAL'

    def _get_crisis_probability(self) -> float:
        """Get current crisis probability."""
        if self.crisis_engine:
            try:
                if hasattr(self.crisis_engine, 'state') and hasattr(self.crisis_engine.state, 'crisis_probability'):
                    probability = self.crisis_engine.state.crisis_probability
                    if isinstance(probability, (int, float)):
                        return float(probability)
                method = getattr(self.crisis_engine, 'get_current_crisis_probability', None)
                if callable(method):
                    probability = method()
                    if isinstance(probability, (int, float)):
                        return float(probability)
            except Exception:
                return 0.0
        return 0.0

    def _compute_caution_score(
        self, market_regime: str, volatility_regime: str, macro_regime: str,
        sentiment_regime: str, econ_activity_regime: str, crisis_probability: float,
        coherence_score: float = 1.0,
    ) -> float:
        """
        Compute a scalar caution score (0.0 = no caution, 1.0 = maximum caution).
        
        Each input contributes a weighted component to the score.
        """
        score = 0.0
        
        # Market regime component (weight: 0.30)
        market_scores = {
            'BULL': 0.0, 'SIDEWAYS': 0.2, 'VOLATILE': 0.5,
            'BEAR': 0.7, 'CRISIS': 1.0
        }
        score += 0.30 * market_scores.get(market_regime, 0.3)
        
        # Volatility regime component (weight: 0.15)
        vol_scores = {
            'LOW_VOL': 0.0, 'NORMAL_VOL': 0.1, 'ELEVATED_VOL': 0.4,
            'HIGH_VOL': 0.7, 'EXTREME_VOL': 1.0
        }
        score += 0.15 * vol_scores.get(volatility_regime, 0.2)
        
        # Macro regime component (weight: 0.20)
        macro_scores = {
            'EXPANSION': 0.0, 'RECOVERY': 0.1, 'NEUTRAL': 0.2,
            'SLOWING': 0.5, 'CONTRACTION': 0.8
        }
        score += 0.20 * macro_scores.get(macro_regime, 0.2)
        
        # Sentiment regime component (weight: 0.15)
        sentiment_scores = {
            'EUPHORIA': 0.2,    # Euphoria = caution (contrarian)
            'OPTIMISM': 0.0,
            'NEUTRAL': 0.1,
            'FEAR': 0.6,
            'PANIC': 1.0,
            'UNAVAILABLE': 0.2
        }
        score += 0.15 * sentiment_scores.get(sentiment_regime, 0.2)
        
        # Economic activity regime component (weight: 0.10)
        econ_scores = {
            'EXPANSION': 0.0, 'RECOVERING': 0.1, 'NEUTRAL': 0.2,
            'SLOWING': 0.5, 'CONTRACTION': 0.8, 'UNAVAILABLE': 0.2
        }
        score += 0.10 * econ_scores.get(econ_activity_regime, 0.2)
        
        # Crisis probability component (weight: 0.10)
        score += 0.10 * min(crisis_probability, 1.0)

        coherence_score = float(max(0.0, min(1.0, coherence_score)))
        if coherence_score < 0.70:
            coherence_penalty = (0.70 - coherence_score) * 0.15
            score += coherence_penalty
            logger.info(
                "Coherence penalty applied: score=%.2f caution+=%.3f",
                coherence_score,
                coherence_penalty,
            )
        
        return min(score, 1.0)

    def _caution_score_to_regime(self, caution_score: float) -> CapitalStructureRegime:
        """Map caution score to CapitalStructureRegime."""
        if caution_score < 0.15:
            return CapitalStructureRegime.FULL_DEPLOYMENT
        elif caution_score < 0.30:
            return CapitalStructureRegime.STANDARD
        elif caution_score < 0.50:
            return CapitalStructureRegime.CAUTIOUS
        elif caution_score < 0.70:
            return CapitalStructureRegime.DEFENSIVE
        else:
            return CapitalStructureRegime.CAPITAL_PRESERVATION

    def _get_base_fractions(self, regime: CapitalStructureRegime) -> dict:
        """Get base fractions from regime table."""
        if regime.value not in self.regime_table:
            raise KeyError(f"Missing capital structure config for regime {regime.value}")

        return dict(self.regime_table[regime.value])

    def _apply_drawdown_modifier(
        self, equity_frac: float, cash_frac: float, current_drawdown_pct: float
    ) -> Tuple[float, float, List[str]]:
        """Apply drawdown-based equity reduction."""
        cfg = self.modifiers.get('drawdown_reduction', {})
        trigger = cfg.get('trigger_drawdown_pct', -8.0)
        reduction_per_pct = cfg.get('equity_reduction_per_pct', 0.03)
        max_reduction = cfg.get('max_equity_reduction', 0.25)
        
        if current_drawdown_pct >= trigger:
            return equity_frac, cash_frac, []
        
        excess_drawdown = abs(current_drawdown_pct - trigger)
        reduction = min(excess_drawdown * reduction_per_pct, max_reduction)
        
        equity_frac = max(equity_frac - reduction, 0.0)
        cash_frac = min(cash_frac + reduction, 1.0)
        
        return equity_frac, cash_frac, [f"DRAWDOWN_REDUCTION({reduction:.2f})"]

    def _apply_recovery_modifier(
        self, equity_frac: float, cash_frac: float, current_drawdown_pct: float
    ) -> Tuple[float, float, List[str]]:
        """Apply recovery-based equity restoration."""
        cfg = self.modifiers.get('recovery_restoration', {})
        activation = cfg.get('activation_drawdown_pct', -3.0)
        restoration_rate = cfg.get('restoration_rate_per_day', 0.01)
        max_restoration = cfg.get('max_restoration_per_day', 0.02)
        
        if current_drawdown_pct >= activation:
            # In recovery zone
            days_elapsed = self.persistent_state.get('recovery_days_elapsed', 0)
            restoration = min(days_elapsed * restoration_rate, max_restoration)
            
            equity_frac = min(equity_frac + restoration, 0.95)
            cash_frac = max(cash_frac - restoration, 0.05)
            
            return equity_frac, cash_frac, [f"RECOVERY_RESTORATION({restoration:.2f})"]
        
        return equity_frac, cash_frac, []

    def _apply_crisis_override(
        self, equity_frac: float, options_frac: float, cash_frac: float,
        current_regime: CapitalStructureRegime, crisis_probability: float
    ) -> Tuple[float, float, float, CapitalStructureRegime, List[str]]:
        """Apply crisis probability override."""
        cfg = self.modifiers.get('crisis_override', {})
        
        if crisis_probability > cfg.get('crisis_prob_preservation', 0.40):
            target = CapitalStructureRegime.CAPITAL_PRESERVATION
        elif crisis_probability > cfg.get('crisis_prob_defensive', 0.25):
            target = CapitalStructureRegime.DEFENSIVE
        elif crisis_probability > cfg.get('crisis_prob_cautious', 0.15):
            target = CapitalStructureRegime.CAUTIOUS
        else:
            return equity_frac, options_frac, cash_frac, current_regime, []
        
        # Only override if more conservative
        regime_order = [
            CapitalStructureRegime.FULL_DEPLOYMENT,
            CapitalStructureRegime.STANDARD,
            CapitalStructureRegime.CAUTIOUS,
            CapitalStructureRegime.DEFENSIVE,
            CapitalStructureRegime.CAPITAL_PRESERVATION,
        ]
        
        if regime_order.index(target) > regime_order.index(current_regime):
            table_entry = self._get_base_fractions(target)
            return (
                table_entry['equity_fraction'],
                table_entry['options_fraction'],
                table_entry['cash_fraction'],
                target,
                [f"CRISIS_OVERRIDE(prob={crisis_probability:.2f},regime={target.value})"]
            )
        
        return equity_frac, options_frac, cash_frac, current_regime, []

    def _apply_nav_size_protection(
        self, equity_frac: float, cash_frac: float, current_nav: float
    ) -> Tuple[float, float, List[str]]:
        """Apply NAV size-based cash protection."""
        cfg = self.modifiers.get('nav_size_protection', {})
        trigger_multiple = cfg.get('trigger_nav_multiple', 1.20)
        cash_per_multiple = cfg.get('cash_per_multiple', 0.02)
        max_additional_cash = cfg.get('max_additional_cash', 0.10)
        
        starting_nav = self.starting_capital_inr
        nav_multiple = current_nav / starting_nav
        
        if nav_multiple <= trigger_multiple:
            return equity_frac, cash_frac, []
        
        excess_multiple = nav_multiple - trigger_multiple
        additional_cash = min(excess_multiple / 0.1 * cash_per_multiple, max_additional_cash)
        
        equity_frac = max(equity_frac - additional_cash, 0.0)
        cash_frac = min(cash_frac + additional_cash, 1.0)
        
        return equity_frac, cash_frac, [f"NAV_PROTECTION({additional_cash:.2f})"]

    def _enforce_hard_limits(
        self, equity_frac: float, options_frac: float, cash_frac: float
    ) -> Tuple[float, float, float]:
        """Enforce hard limits on capital fractions."""
        # Clip to limits
        equity_frac = max(
            self.hard_limits.get('min_equity_fraction', 0.10),
            min(equity_frac, self.hard_limits.get('max_equity_fraction', 0.95))
        )
        options_frac = max(
            self.hard_limits.get('min_options_fraction', 0.00),
            min(options_frac, self.hard_limits.get('max_options_fraction', 0.25))
        )
        cash_frac = max(
            self.hard_limits.get('min_cash_fraction', 0.05),
            cash_frac
        )
        
        # Redistribute excess to cash (conservative choice)
        total = equity_frac + options_frac + cash_frac
        if total > 1.0:
            excess = total - 1.0
            cash_frac = max(cash_frac - excess, self.hard_limits.get('min_cash_fraction', 0.05))
        
        return equity_frac, options_frac, cash_frac

    def _build_rationale(
        self, regime: CapitalStructureRegime, caution_score: float, modifiers: List[str]
    ) -> str:
        """Build human-readable rationale for the decision."""
        base_reasons = {
            CapitalStructureRegime.FULL_DEPLOYMENT: "All regime signals aligned positively",
            CapitalStructureRegime.STANDARD: "Normal market conditions",
            CapitalStructureRegime.CAUTIOUS: "Mixed or elevated risk signals",
            CapitalStructureRegime.DEFENSIVE: "Adverse regime conditions",
            CapitalStructureRegime.CAPITAL_PRESERVATION: "Crisis or extreme regime detected",
        }
        
        rationale = base_reasons.get(regime, "Unknown regime")
        
        if modifiers:
            rationale += f". Modifiers applied: {', '.join(modifiers)}"
        
        return rationale

    def _compute_governance_confidence(
        self, caution_score: float, modifiers: List[str], coherence_score: float = 1.0
    ) -> float:
        """Compute confidence in the governance decision."""
        # Base confidence from caution score clarity
        if caution_score < 0.15 or caution_score > 0.85:
            base_confidence = 0.9
        elif caution_score < 0.30 or caution_score > 0.70:
            base_confidence = 0.7
        else:
            base_confidence = 0.5
        
        # Reduce confidence if many modifiers applied
        modifier_penalty = len(modifiers) * 0.05
        confidence = max(0.1, min(1.0, base_confidence - modifier_penalty))
        confidence *= (0.7 + 0.3 * float(max(0.0, min(1.0, coherence_score))))
        return max(0.1, min(1.0, confidence))

    def increment_recovery_counter(
        self,
        current_drawdown_pct: float,
        current_regime: Optional[str] = None,
    ) -> bool:
        """
        Increment recovery_days_elapsed when drawdown has resolved and posture is no longer defensive.
        """
        if float(current_drawdown_pct) < -3.0:
            logger.debug("Recovery counter not incremented: drawdown %.2f still below activation", current_drawdown_pct)
            return False

        regime_name = str(current_regime or self.persistent_state.get('last_decision_regime', 'STANDARD')).upper()
        if regime_name in {'DEFENSIVE', 'CAPITAL_PRESERVATION'}:
            logger.debug("Recovery counter not incremented: regime %s still defensive", regime_name)
            return False

        standard_equity = float(
            self.regime_table.get(CapitalStructureRegime.STANDARD.value, {}).get('equity_fraction', 0.75)
        )
        last_equity_fraction = float(self.persistent_state.get('last_equity_fraction', standard_equity))
        if last_equity_fraction >= standard_equity:
            logger.debug(
                "Recovery counter not incremented: last equity %.2f already at/above standard %.2f",
                last_equity_fraction,
                standard_equity,
            )
            return False

        current = int(self.persistent_state.get('recovery_days_elapsed', 0) or 0)
        self.persistent_state['recovery_days_elapsed'] = current + 1
        self._save_persistent_state()
        logger.info(
            "Recovery day %s recorded (drawdown=%.2f regime=%s)",
            current + 1,
            current_drawdown_pct,
            regime_name,
        )
        return True

    def reset_recovery_counter(self) -> None:
        """Reset the recovery clock when drawdown re-triggers."""
        previous = int(self.persistent_state.get('recovery_days_elapsed', 0) or 0)
        self.persistent_state['recovery_days_elapsed'] = 0
        self._save_persistent_state()
        logger.info("Recovery counter reset (%s -> 0)", previous)

    def compute_and_apply(
        self, unified_state, convex_allocator=None, capital_policy_instance=None
    ) -> CapitalStructure:
        """
        Compute capital structure and apply it to allocators.
        
        This is the main execution method with side effects.
        """
        # Compute structure
        structure = self.compute_capital_structure(unified_state)
        
        logger.info(
            f"Governor decision: {structure.capital_structure_regime.value} — "
            f"Equity={structure.equity_fraction:.1%}, "
            f"Options={structure.options_fraction:.1%}, "
            f"Cash={structure.cash_fraction:.1%}"
        )
        
        # Apply to allocators
        if convex_allocator:
            convex_allocator._effective_capital = structure.equity_budget_inr
            logger.info(f"Injected equity budget: ₹{structure.equity_budget_inr:,.0f}")
        
        if capital_policy_instance:
            capital_policy_instance._options_budget_inr = structure.options_budget_inr
            logger.info(f"Injected options budget: ₹{structure.options_budget_inr:,.0f}")
        
        # Write to allocation history
        self._write_allocation_history(structure)
        
        # Update persistent state
        self._update_persistent_state(structure)
        
        # Emit event
        if self.event_bus:
            self.event_bus.emit('CAPITAL_STRUCTURE_SET', structure.to_dict())
        
        self.current_structure = structure
        return structure

    def _write_allocation_history(self, structure: CapitalStructure) -> None:
        """Write decision to allocation history."""
        import pandas as pd
        
        history_row = {
            'decision_date': [structure.valid_for_date],
            'computed_at': [structure.computed_at],
            'capital_structure_regime': [structure.capital_structure_regime.value],
            'equity_fraction': [structure.equity_fraction],
            'options_fraction': [structure.options_fraction],
            'cash_fraction': [structure.cash_fraction],
            'equity_budget_inr': [structure.equity_budget_inr],
            'options_budget_inr': [structure.options_budget_inr],
            'caution_score': [self._compute_caution_score(
                structure.market_regime, structure.volatility_regime,
                structure.macro_regime, structure.sentiment_regime,
                structure.economic_activity_regime, structure.crisis_probability
            )],
            'crisis_probability': [structure.crisis_probability],
            'market_regime': [structure.market_regime],
            'macro_regime': [structure.macro_regime],
            'sentiment_regime': [structure.sentiment_regime],
            'econ_activity_regime': [structure.economic_activity_regime],
            'current_drawdown_pct': [structure.current_drawdown_pct],
            'modifiers_applied': [json.dumps(structure.modifiers_applied)],
            'primary_rationale': [structure.primary_rationale],
            'is_intraday_escalation': [False],
            'is_manual_override': [False],
        }
        
        history_df = pd.DataFrame(history_row)
        
        # Append to existing file or create new
        if self.allocation_history_file.exists():
            try:
                existing = pd.read_parquet(self.allocation_history_file)
                history_df = pd.concat([existing, history_df], ignore_index=True)
            except Exception:
                pass
        
        self.allocation_history_file.parent.mkdir(parents=True, exist_ok=True)
        history_df.to_parquet(self.allocation_history_file, index=False)

    def _update_persistent_state(self, structure: CapitalStructure) -> None:
        """Update persistent governor state."""
        last_regime = self.persistent_state.get('last_decision_regime')
        current_regime = structure.capital_structure_regime.value
        
        if last_regime != current_regime:
            self.persistent_state['days_in_current_regime'] = 1
            self.persistent_state['regime_changes_this_week'] = \
                self.persistent_state.get('regime_changes_this_week', 0) + 1
        else:
            self.persistent_state['days_in_current_regime'] = \
                self.persistent_state.get('days_in_current_regime', 0) + 1
        
        self.persistent_state['last_decision_date'] = structure.valid_for_date.isoformat()
        self.persistent_state['last_decision_regime'] = current_regime
        self.persistent_state['current_regime'] = current_regime
        self.persistent_state['last_equity_fraction'] = float(structure.equity_fraction)
        self.persistent_state['drawdown_at_last_decision'] = structure.current_drawdown_pct
        
        self._save_persistent_state()

    def check_intraday_escalation(
        self, unified_state, current_structure: Optional[CapitalStructure] = None
    ) -> Optional[CapitalStructure]:
        """
        Check if intraday regime change requires more conservative structure.
        
        Intraday changes can ONLY move toward more conservative structures.
        Returns None if no escalation needed.
        """
        current_structure = current_structure or self.current_structure
        if current_structure is None:
            return None

        new_structure = self.compute_capital_structure(unified_state)
        
        regime_order = [
            CapitalStructureRegime.FULL_DEPLOYMENT,
            CapitalStructureRegime.STANDARD,
            CapitalStructureRegime.CAUTIOUS,
            CapitalStructureRegime.DEFENSIVE,
            CapitalStructureRegime.CAPITAL_PRESERVATION,
        ]
        
        current_idx = regime_order.index(current_structure.capital_structure_regime)
        new_idx = regime_order.index(new_structure.capital_structure_regime)
        
        if new_idx > current_idx:
            # More conservative - apply escalation
            logger.warning(
                f"Intraday escalation: {current_structure.capital_structure_regime.value} → "
                f"{new_structure.capital_structure_regime.value} "
                f"(crisis_prob={new_structure.crisis_probability:.2f})"
            )
            
            new_structure.overrides_active.append('INTRADAY_ESCALATION')
            
            if self.event_bus:
                self.event_bus.emit('INTRADAY_ESCALATION', new_structure.to_dict())
            
            self.current_structure = new_structure
            return new_structure
        
        return None

    def apply_manual_override(
        self,
        equity_fraction: float,
        options_fraction: float,
        cash_fraction: float,
        reason: str,
        unified_state,
    ) -> CapitalStructure:
        """Apply an auditable manual override while still honoring hard limits."""
        equity_fraction, options_fraction, cash_fraction = self._enforce_hard_limits(
            equity_fraction,
            options_fraction,
            cash_fraction,
        )

        total = equity_fraction + options_fraction + cash_fraction
        if total < 1.0:
            cash_fraction += 1.0 - total
        elif total > 1.0:
            excess = total - 1.0
            equity_floor = self.hard_limits.get('min_equity_fraction', 0.10)
            options_floor = self.hard_limits.get('min_options_fraction', 0.00)
            cash_floor = self.hard_limits.get('min_cash_fraction', 0.02)

            equity_reduction = min(excess, max(0.0, equity_fraction - equity_floor))
            equity_fraction -= equity_reduction
            excess -= equity_reduction

            if excess > 0:
                options_reduction = min(excess, max(0.0, options_fraction - options_floor))
                options_fraction -= options_reduction
                excess -= options_reduction

            if excess > 0:
                cash_fraction = max(cash_floor, cash_fraction - excess)

        current_nav = unified_state.pnl_state.current_nav_inr or self.starting_capital_inr
        computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        market_close = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)

        structure = CapitalStructure(
            equity_fraction=equity_fraction,
            options_fraction=options_fraction,
            cash_fraction=cash_fraction,
            total_capital_inr=current_nav,
            equity_budget_inr=equity_fraction * current_nav,
            options_budget_inr=options_fraction * current_nav,
            cash_reserve_inr=cash_fraction * current_nav,
            capital_structure_regime=(
                CapitalStructureRegime.CAPITAL_PRESERVATION
                if cash_fraction >= 0.70 else CapitalStructureRegime.DEFENSIVE
            ),
            confidence=1.0,
            market_regime=unified_state.market.regime,
            volatility_regime=unified_state.market.volatility_regime,
            macro_regime=getattr(unified_state.macro, 'regime', 'NEUTRAL'),
            sentiment_regime=(
                unified_state.sentiment.market_sentiment_regime.value
                if hasattr(unified_state.sentiment.market_sentiment_regime, 'value')
                else str(unified_state.sentiment.market_sentiment_regime)
            ),
            economic_activity_regime=(
                unified_state.alternative_data.economic_activity_regime.value
                if hasattr(unified_state.alternative_data.economic_activity_regime, 'value')
                else str(unified_state.alternative_data.economic_activity_regime)
            ),
            crisis_probability=self._get_crisis_probability(),
            current_drawdown_pct=unified_state.pnl_state.current_drawdown_pct,
            current_nav_inr=current_nav,
            primary_rationale=f"Manual override applied: {reason}",
            modifiers_applied=[],
            overrides_active=[f"MANUAL_OVERRIDE({reason})"],
            valid_for_date=datetime.now(),
            expires_at=market_close,
            computed_at=computed_at,
        )

        structure.validate()
        self.current_structure = structure
        return structure

    def get_governance_explanation(self, structure: CapitalStructure) -> str:
        """Get human-readable explanation of the capital structure decision."""
        explanation = (
            f"Capital structure is set to {structure.capital_structure_regime.value} "
            f"({structure.equity_fraction:.0%} equity, {structure.options_fraction:.0%} options, "
            f"{structure.cash_fraction:.0%} cash). "
            f"Primary driver: {structure.primary_rationale}. "
            f"Confidence: {structure.confidence:.0%}. "
            f"This structure will persist through today's trading session."
        )
        
        return explanation
