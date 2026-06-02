"""
ValuationBridge — Synchronizes valuation engine state into UnifiedState.

The PortfolioValuationStateEngine in src/valuation/state.py tracks:
- Per-ticker fair values and confidence levels
- Portfolio-level weighted valuation metrics
- Valuation change attribution

The bridge pushes portfolio-level metrics into UnifiedState. Per-ticker valuation
details stay private to the valuation engine.

External consumers (dashboard, narrative engine, risk controller) that need to know
"is the portfolio cheap or expensive overall?" can read UnifiedState.valuation_state
without knowing the valuation engine exists.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

from src.core.state_authority import StateAuthority, StateUpdate, WritePriority

logger = logging.getLogger(__name__)


class ValuationStateBridge:
    """Synchronizes valuation engine state into UnifiedState."""
    
    def __init__(
        self,
        state_authority: StateAuthority,
        config: Optional[Dict] = None
    ):
        """
        Initialize the valuation bridge.
        
        Args:
            state_authority: StateAuthority instance for pushing updates
            config: Optional configuration dict
        """
        self.state_authority = state_authority
        self.config = config or {}

        self.state_authority.register_writer(
            writer_id='valuation_bridge',
            allowed_sections=['valuation_state'],
            priority=WritePriority.BRIDGE_SYNC,
        )
        
        logger.info("ValuationStateBridge initialized")
    
    def push_valuation_summary(
        self,
        valuation_state_df: pd.DataFrame,
        posterior_df: Optional[pd.DataFrame] = None
    ) -> None:
        """
        Called by valuation engine after each valuation update cycle.
        
        Pushes portfolio-level valuation metrics to UnifiedState.valuation_state.
        
        Args:
            valuation_state_df: DataFrame from PortfolioValuationStateEngine.compute()
            posterior_df: Optional posterior DataFrame with per-ticker valuations
        """
        try:
            if valuation_state_df.empty:
                logger.warning("Valuation state DataFrame is empty")
                return
            
            # Get latest valuation state
            latest = valuation_state_df.iloc[-1]
            
            # Extract metrics
            market_percentile = latest.get('market_percentile', 0.5)
            sector_dispersion = latest.get('sector_dispersion', 0.0)
            aggregate_gap_mean = latest.get('aggregate_gap_mean', 0.0)
            aggregate_gap_std = latest.get('aggregate_gap_std', 0.0)
            bubble_probability = latest.get('bubble_probability', 0.0)
            valuation_regime = latest.get('valuation_regime', 'unknown')
            
            # Compute additional metrics
            portfolio_discount_to_fair_value = aggregate_gap_mean  # Gap is (fair - market) / fair
            
            # Compute valuation confidence and coverage
            valuation_confidence = 0.0
            tickers_with_fair_value = 0
            tickers_in_portfolio = 0
            
            if posterior_df is not None and not posterior_df.empty:
                # Count tickers with valid fair values
                valid_valuations = posterior_df[
                    posterior_df['posterior_gap'].notna()
                ]
                tickers_with_fair_value = len(valid_valuations)
                tickers_in_portfolio = len(posterior_df)
                
                # Compute average confidence if available
                if 'confidence' in posterior_df.columns:
                    valuation_confidence = float(
                        posterior_df['confidence'].mean()
                    )
                else:
                    # Estimate confidence from gap std
                    valuation_confidence = max(0.0, 1.0 - (aggregate_gap_std / 0.5))
            
            valuation_coverage_pct = (
                tickers_with_fair_value / tickers_in_portfolio
                if tickers_in_portfolio > 0
                else 0.0
            )
            
            # Compute margin of safety
            avg_margin_of_safety_pct = aggregate_gap_mean * 100.0  # Convert to percentage
            
            # Map regime to simplified categories
            regime_map = {
                'bubble_risk': 'EXPENSIVE',
                'overvalued': 'EXPENSIVE',
                'deep_value': 'CHEAP',
                'balanced': 'FAIR_VALUE',
                'unknown': 'UNKNOWN'
            }
            simplified_regime = regime_map.get(valuation_regime, 'MIXED')
            
            # Build updates
            updates = [
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='portfolio_weighted_pe',
                    new_value=0.0,  # TODO: Compute from posterior if available
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='portfolio_weighted_pb',
                    new_value=0.0,  # TODO: Compute from posterior if available
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='portfolio_discount_to_fair_value',
                    new_value=float(portfolio_discount_to_fair_value),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='valuation_confidence',
                    new_value=float(valuation_confidence),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='tickers_with_fair_value',
                    new_value=int(tickers_with_fair_value),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='tickers_in_portfolio',
                    new_value=int(tickers_in_portfolio),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='valuation_coverage_pct',
                    new_value=float(valuation_coverage_pct),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='valuation_regime',
                    new_value=simplified_regime,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='avg_margin_of_safety_pct',
                    new_value=float(avg_margin_of_safety_pct),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
                StateUpdate(
                    writer_id='valuation_bridge',
                    section='valuation_state',
                    field_path='last_valuation_run',
                    new_value=datetime.utcnow(),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Valuation update'
                ),
            ]
            
            # Apply batch update
            applied = self.state_authority.batch_update(updates)
            logger.info(
                f"Valuation summary sync: {applied}/{len(updates)} fields synced, "
                f"regime={simplified_regime}, discount={portfolio_discount_to_fair_value:.2%}"
            )
            
        except Exception as e:
            logger.error(f"Failed to push valuation summary: {e}", exc_info=True)
