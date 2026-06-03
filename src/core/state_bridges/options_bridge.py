"""
Options Bridge — Synchronizes options system state into UnifiedState.

This bridge reads from options internals and pushes summaries to UnifiedState
via StateAuthority. Called after every position change and mode transition.
"""

import logging
from datetime import datetime
from typing import Optional

from ..state_authority import StateAuthority, StateUpdate, WritePriority

logger = logging.getLogger(__name__)


class OptionsStateBridge:
    """
    Synchronizes options system state into UnifiedState.
    
    The options system maintains rich internal state in position_manager.py
    and mode_controller.py. External consumers need a summary of:
    - Current options positions
    - Portfolio-level Greeks
    - Current operating mode
    - Capital deployment
    - Risk metrics
    """
    
    def __init__(self, position_manager, mode_controller, greeks_aggregator,
                 state_authority: StateAuthority):
        """
        Initialize the Options Bridge.
        
        Args:
            position_manager: Options position manager instance
            mode_controller: Options mode controller instance
            greeks_aggregator: Greeks aggregation component
            state_authority: State authority for updates
        """
        self.position_manager = position_manager
        self.mode_controller = mode_controller
        self.greeks_aggregator = greeks_aggregator
        self.state_authority = state_authority
        
        # Register as a writer
        self.state_authority.register_writer(
            writer_id='options_bridge',
            allowed_sections=['portfolio', 'risk'],
            priority=WritePriority.BRIDGE_SYNC
        )
        
        logger.info("OptionsStateBridge initialized")
    
    def push_position_update(self, reason: str = 'POSITION_CHANGE') -> None:
        """
        Push options position summary to UnifiedState.
        
        Called by position_manager after any position change.
        """
        try:
            # Read positions from position manager
            positions = self._get_position_summary()
            
            # Compute portfolio-level Greeks
            greeks = self._get_portfolio_greeks()
            
            # Compute risk metrics
            risk_metrics = self._get_risk_metrics()
            
            # Get current mode
            current_mode = self.mode_controller._current_mode if hasattr(self.mode_controller, '_current_mode') else 'UNKNOWN'
            
            # Push to UnifiedState.portfolio
            portfolio_updates = [
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_positions',
                    new_value=positions,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=f'Options position update: {reason}'
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_position_count',
                    new_value=len(positions),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_delta',
                    new_value=greeks.get('net_delta', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_gamma',
                    new_value=greeks.get('net_gamma', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_vega',
                    new_value=greeks.get('net_vega', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_theta',
                    new_value=greeks.get('net_theta', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_premium_at_risk',
                    new_value=risk_metrics.get('premium_at_risk', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_system_mode',
                    new_value=current_mode,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
            ]
            
            self.state_authority.batch_update(portfolio_updates)
            
            # Push to UnifiedState.risk
            risk_updates = [
                StateUpdate(
                    writer_id='options_bridge',
                    section='risk',
                    field_path='options_delta_exposure_inr',
                    new_value=risk_metrics.get('delta_exposure_inr', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='risk',
                    field_path='options_vega_exposure_inr',
                    new_value=risk_metrics.get('vega_exposure_inr', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='risk',
                    field_path='options_margin_utilization',
                    new_value=risk_metrics.get('margin_utilization', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason=reason
                ),
            ]
            
            self.state_authority.batch_update(risk_updates)
            
            logger.debug(f"Pushed options position update: {len(positions)} positions, mode={current_mode}")
            
        except Exception as e:
            logger.error(f"Failed to push options position update: {e}")
    
    def push_mode_update(self, new_mode: str, reason: str) -> None:
        """
        Push mode transition to UnifiedState.
        
        Called by mode_controller after any mode transition.
        """
        try:
            update = StateUpdate(
                writer_id='options_bridge',
                section='portfolio',
                field_path='options_system_mode',
                new_value=new_mode,
                priority=WritePriority.BRIDGE_SYNC,
                source='LIVE',
                reason=f'Mode transition: {reason}'
            )
            
            self.state_authority.update(update)
            
            # Update risk state based on mode
            if new_mode in ['SURVIVAL_CORE', 'RECOVERY']:
                risk_update = StateUpdate(
                    writer_id='options_bridge',
                    section='risk',
                    field_path='options_trading_suspended',
                    new_value=True,
                    priority=WritePriority.EMERGENCY,
                    source='LIVE',
                    reason=f'Mode {new_mode} - trading suspended'
                )
                self.state_authority.update(risk_update)
            
            logger.info(f"Pushed options mode update: {new_mode}")
            
        except Exception as e:
            logger.error(f"Failed to push mode update: {e}")
    
    def push_greeks_snapshot(self) -> None:
        """
        Push fresh Greeks snapshot.
        
        Called every 5 minutes during market hours.
        """
        try:
            greeks = self._get_portfolio_greeks()
            
            updates = [
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_delta',
                    new_value=greeks.get('net_delta', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason='Greeks snapshot'
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_gamma',
                    new_value=greeks.get('net_gamma', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason='Greeks snapshot'
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_vega',
                    new_value=greeks.get('net_vega', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason='Greeks snapshot'
                ),
                StateUpdate(
                    writer_id='options_bridge',
                    section='portfolio',
                    field_path='options_net_theta',
                    new_value=greeks.get('net_theta', 0.0),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='LIVE',
                    reason='Greeks snapshot'
                ),
            ]
            
            self.state_authority.batch_update(updates)
            
        except Exception as e:
            logger.error(f"Failed to push Greeks snapshot: {e}")
    
    def _get_position_summary(self) -> dict:
        """Get summary of current options positions."""
        if not hasattr(self.position_manager, 'positions'):
            return {}
        
        positions = {}
        for pos_id, pos in self.position_manager.positions.items():
            positions[pos_id] = {
                'ticker': getattr(pos, 'underlying', ''),
                'option_type': getattr(pos, 'option_type', ''),
                'strike': getattr(pos, 'strike', 0.0),
                'expiry': getattr(pos, 'expiry', ''),
                'quantity': getattr(pos, 'quantity', 0),
                'avg_price': getattr(pos, 'avg_price', 0.0),
                'current_price': getattr(pos, 'current_price', 0.0),
                'pnl': getattr(pos, 'pnl', 0.0),
            }
        
        return positions
    
    def _get_portfolio_greeks(self) -> dict:
        """Get portfolio-level Greeks."""
        if self.greeks_aggregator:
            return {
                'net_delta': getattr(self.greeks_aggregator, 'net_delta', 0.0),
                'net_gamma': getattr(self.greeks_aggregator, 'net_gamma', 0.0),
                'net_vega': getattr(self.greeks_aggregator, 'net_vega', 0.0),
                'net_theta': getattr(self.greeks_aggregator, 'net_theta', 0.0),
            }
        
        return {'net_delta': 0.0, 'net_gamma': 0.0, 'net_vega': 0.0, 'net_theta': 0.0}
    
    def _get_risk_metrics(self) -> dict:
        """Get options risk metrics."""
        # These would come from the options risk system
        # For now, return defaults
        return {
            'premium_at_risk': 0.0,
            'delta_exposure_inr': 0.0,
            'vega_exposure_inr': 0.0,
            'margin_utilization': 0.0,
        }
