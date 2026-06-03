"""
StrategyOrchestrator — Governs runtime strategy weights and signal aggregation.

The orchestrator answers the question: "Right now, given the current regime,
which strategies should be active and at what weight relative to each other?"

It does NOT compute signals. Signals come from the intelligence stack's individual
strategy modules. The orchestrator takes those signals and determines how to combine
them, based on:
  1. Current regime (from UnifiedState)
  2. Tribunal capital weights (from StrategyTribunal)
  3. Redundancy flags (from StrategyRedundancy)
  4. Current strategy status (from StrategyRegistry)
  5. Strategy tailwinds (from data/intelligence/strategy_tailwinds.parquet)

This is the component that intelligence_stack.py should delegate to for weight
computation, rather than computing weights inline.
"""

from typing import Dict, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class StrategyOrchestrator:
    """Governs runtime strategy weights and signal aggregation."""
    
    def __init__(
        self,
        registry,
        tribunal,
        redundancy,
        config: Optional[Dict] = None
    ):
        """
        Args:
            registry: StrategyRegistry instance
            tribunal: StrategyTribunal instance
            redundancy: StrategyRedundancyDetector instance
            config: Configuration dict
        """
        self._registry = registry
        self._tribunal = tribunal
        self._redundancy = redundancy
        self._config = config or {}
        
        # Paths
        self._tailwinds_path = Path("data/intelligence/strategy_tailwinds.parquet")
        self._regime_labels_path = Path("data/processed/regime_labels.parquet")
        
        # Cache
        self._tailwinds_cache = None
        self._tailwinds_cache_time = None
    
    def compute_strategy_weights(self, unified_state) -> Dict[str, float]:
        """
        Core method. Takes the current UnifiedState and returns a dict of
        {strategy_id: weight} where weights sum to 1.0 across all active strategies.
        
        Weight computation pipeline:
        1. Get all ACTIVE and PROBATION strategies from the registry
        2. Get base capital weights from the tribunal (Bayesian posterior allocations)
        3. Apply regime-conditional modifiers from strategy_tailwinds.parquet
        4. Zero out REDUNDANT strategies
        5. Apply PROBATION penalty
        6. Re-normalize so weights sum to 1.0
        7. Return the final weight dict
        """
        logger.debug("Computing strategy weights")
        
        # Step 1: Get active strategies
        active_strategies = self._registry.get_active_strategies()
        
        if not active_strategies:
            logger.warning("No active strategies found")
            return {}
        
        # Step 2: Get base capital weights from tribunal
        base_weights = self._tribunal.get_capital_weights()
        
        # Initialize weights dict
        weights = {}
        
        for strategy in active_strategies:
            strategy_id = strategy.strategy_id
            
            # Get base weight (default to equal weight if not in tribunal)
            base_weight = base_weights.get(strategy_id, 1.0 / len(active_strategies))
            
            # Step 3: Apply regime-conditional modifier
            regime_modifier = self._get_regime_modifier(strategy_id, unified_state)
            
            # Step 4: Zero out REDUNDANT strategies
            if strategy.status == strategy.status.__class__.REDUNDANT:
                weights[strategy_id] = 0.0
                continue
            
            # Step 5: Apply PROBATION penalty
            if strategy.status == strategy.status.__class__.PROBATION:
                probation_factor = self._config.get('probation_weight_factor', 0.4)
                adjusted_weight = base_weight * regime_modifier * probation_factor
            else:
                adjusted_weight = base_weight * regime_modifier
            
            weights[strategy_id] = adjusted_weight
        
        # Step 6: Re-normalize
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        else:
            # Fallback to equal weights
            n_strategies = len([w for w in weights.values() if w > 0])
            if n_strategies > 0:
                equal_weight = 1.0 / n_strategies
                weights = {k: equal_weight if v > 0 else 0.0 for k, v in weights.items()}
        
        logger.debug(f"Computed weights for {len(weights)} strategies")
        
        return weights
    
    def get_active_strategy_ids(self, unified_state) -> list:
        """
        Returns the list of strategy IDs that are currently active given the regime.
        A strategy can be in the registry as ACTIVE but conditionally inactive in
        certain regimes.
        """
        active_strategies = self._registry.get_active_strategies()
        
        active_ids = []
        for strategy in active_strategies:
            if self.compute_regime_activation(strategy.strategy_id, unified_state):
                active_ids.append(strategy.strategy_id)
        
        return active_ids
    
    def compute_regime_activation(self, strategy_id: str, unified_state) -> bool:
        """
        Checks whether a specific strategy should be active in the current regime.
        Uses the regime_activations dict from the strategy's registry record.
        """
        try:
            strategy = self._registry.get(strategy_id)
            
            # Get current regime
            current_regime = self._get_current_regime(unified_state)
            
            # Check regime_activations dict
            if current_regime in strategy.regime_activations:
                return strategy.regime_activations[current_regime]
            
            # Default: active in all regimes if not specified
            return True
            
        except Exception as e:
            logger.warning(f"Could not check regime activation for {strategy_id}: {e}")
            return True  # Default to active
    
    def update_strategy_tailwinds(self, as_of_date: datetime) -> None:
        """
        Recomputes and rewrites data/intelligence/strategy_tailwinds.parquet using
        the current (updated) regime labels from data/processed/regime_labels.parquet.
        
        This is the method that needs to run after Gap 2 and Gap 3 regime improvements,
        because the regime labels have changed and the tailwinds file needs to be
        recomputed against the new labels.
        
        The recomputation uses the strategy performance history in the registry:
        for each strategy, for each historical regime period, compute the average IC.
        This becomes the new tailwind score.
        """
        logger.info(f"Recomputing strategy tailwinds as of {as_of_date.date()}")
        
        try:
            # Load regime labels
            if not self._regime_labels_path.exists():
                logger.warning("Regime labels file not found, cannot update tailwinds")
                return
            
            regime_df = pd.read_parquet(self._regime_labels_path)
            
            # Get all strategies
            all_strategies = list(self._registry.strategies.values())
            
            if not all_strategies:
                logger.warning("No strategies in registry, cannot update tailwinds")
                return
            
            # Build tailwinds dataframe
            tailwinds_records = []
            
            for strategy in all_strategies:
                # Get performance history
                if not strategy.performance_history:
                    continue
                
                # Group by regime and calculate average IC
                regime_ics = {}
                
                for perf in strategy.performance_history:
                    for regime, ic in perf.regime_conditional_ics.items():
                        if regime not in regime_ics:
                            regime_ics[regime] = []
                        regime_ics[regime].append(ic)
                
                # Calculate average IC per regime
                for regime, ic_list in regime_ics.items():
                    avg_ic = np.mean(ic_list)
                    
                    tailwinds_records.append({
                        'strategy_id': strategy.strategy_id,
                        'strategy_family': strategy.family.value,
                        'regime': regime,
                        'tailwind_score': avg_ic,
                        'n_observations': len(ic_list),
                        'as_of_date': as_of_date
                    })
            
            if tailwinds_records:
                # Create dataframe
                tailwinds_df = pd.DataFrame(tailwinds_records)
                
                # Save to parquet
                self._tailwinds_path.parent.mkdir(parents=True, exist_ok=True)
                tailwinds_df.to_parquet(self._tailwinds_path, index=False)
                
                # Clear cache
                self._tailwinds_cache = None
                self._tailwinds_cache_time = None
                
                logger.info(
                    f"Updated strategy tailwinds: {len(tailwinds_records)} records "
                    f"for {len(all_strategies)} strategies"
                )
            else:
                logger.warning("No tailwinds records generated")
                
        except Exception as e:
            logger.error(f"Failed to update strategy tailwinds: {e}")
    
    def get_orchestrator_explanation(self, unified_state) -> Dict:
        """
        Returns a human-readable explanation of the current weight distribution,
        suitable for the dashboard and the narrative engine.
        """
        weights = self.compute_strategy_weights(unified_state)
        current_regime = self._get_current_regime(unified_state)
        
        # Get regime-inactive strategies
        all_active = self._registry.get_active_strategies()
        regime_inactive = [
            s.strategy_id for s in all_active
            if not self.compute_regime_activation(s.strategy_id, unified_state)
        ]
        
        # Get probation strategies
        probation_strategies = [
            s.strategy_id for s in all_active
            if s.status == s.status.__class__.PROBATION
        ]
        
        # Build weight rationale
        weight_rationale = {}
        for strategy_id, weight in weights.items():
            try:
                strategy = self._registry.get(strategy_id)
                
                reasons = []
                if strategy.status == strategy.status.__class__.PROBATION:
                    reasons.append("On probation - reduced allocation")
                
                regime_modifier = self._get_regime_modifier(strategy_id, unified_state)
                if regime_modifier > 1.1:
                    reasons.append(f"Strong regime fit ({regime_modifier:.2f}x)")
                elif regime_modifier < 0.9:
                    reasons.append(f"Weak regime fit ({regime_modifier:.2f}x)")
                
                if not reasons:
                    reasons.append("Normal allocation")
                
                weight_rationale[strategy_id] = "; ".join(reasons)
                
            except Exception as e:
                weight_rationale[strategy_id] = "Unknown"
        
        return {
            'current_regime_combination': current_regime,
            'strategy_weights': weights,
            'weight_rationale': weight_rationale,
            'regime_inactive_strategies': regime_inactive,
            'probation_strategies': probation_strategies,
            'total_active_strategies': len(weights),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _get_regime_modifier(self, strategy_id: str, unified_state) -> float:
        """
        Get regime-conditional modifier from strategy_tailwinds.parquet.
        Returns a multiplier (1.0 = neutral, >1.0 = favorable, <1.0 = unfavorable).
        """
        try:
            # Load tailwinds (with caching)
            tailwinds_df = self._load_tailwinds()
            
            if tailwinds_df is None or tailwinds_df.empty:
                return 1.0
            
            # Get current regime
            current_regime = self._get_current_regime(unified_state)
            
            # Look up tailwind score
            mask = (
                (tailwinds_df['strategy_id'] == strategy_id) &
                (tailwinds_df['regime'] == current_regime)
            )
            
            matching = tailwinds_df[mask]
            
            if matching.empty:
                return 1.0
            
            tailwind_score = matching.iloc[0]['tailwind_score']
            
            # Convert IC to multiplier
            # IC of 0.03 = 1.0x (neutral)
            # IC of 0.06 = 1.5x (favorable)
            # IC of 0.00 = 0.5x (unfavorable)
            baseline_ic = 0.03
            multiplier = 1.0 + (tailwind_score - baseline_ic) / baseline_ic
            
            # Clamp between 0.3x and 2.0x
            return max(0.3, min(2.0, multiplier))
            
        except Exception as e:
            logger.warning(f"Could not get regime modifier for {strategy_id}: {e}")
            return 1.0
    
    def _get_current_regime(self, unified_state) -> str:
        """
        Extract current regime from UnifiedState.
        Combines market_regime + sentiment_regime + economic_activity_regime.
        """
        try:
            # Get market regime
            market_regime = getattr(unified_state.market, 'regime', 'unknown')
            
            # Get sentiment regime if available
            sentiment_regime = 'neutral'
            if hasattr(unified_state, 'sentiment') and unified_state.sentiment.is_fresh:
                sentiment_regime = unified_state.sentiment.market_sentiment_regime.value
            
            # Get economic activity regime if available
            economic_regime = 'normal'
            if hasattr(unified_state, 'alternative_data') and unified_state.alternative_data.is_fresh:
                economic_regime = getattr(
                    unified_state.alternative_data,
                    'economic_activity_regime',
                    'normal'
                )
            
            # Combine regimes
            combined_regime = f"{market_regime}_{sentiment_regime}_{economic_regime}"
            
            return combined_regime
            
        except Exception as e:
            logger.warning(f"Could not determine current regime: {e}")
            return "unknown"
    
    def _load_tailwinds(self) -> Optional[pd.DataFrame]:
        """Load strategy tailwinds with caching."""
        # Check cache (refresh every 1 hour)
        if self._tailwinds_cache is not None:
            if self._tailwinds_cache_time:
                age_seconds = (datetime.utcnow() - self._tailwinds_cache_time).total_seconds()
                if age_seconds < 3600:  # 1 hour
                    return self._tailwinds_cache
        
        # Load from disk
        try:
            if not self._tailwinds_path.exists():
                logger.debug("Strategy tailwinds file not found")
                return None
            
            df = pd.read_parquet(self._tailwinds_path)
            
            # Update cache
            self._tailwinds_cache = df
            self._tailwinds_cache_time = datetime.utcnow()
            
            return df
            
        except Exception as e:
            logger.warning(f"Could not load strategy tailwinds: {e}")
            return None
