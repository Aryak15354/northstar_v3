"""
ShadowBridge — Synchronizes shadow trading state into UnifiedState.

The shadow system runs in parallel with the live system. Its state is stored in:
- data/shadow_reality/shadow_portfolio_state.parquet
- data/shadow_reality/shadow_execution_log.parquet

The bridge reads the current shadow state and pushes a summary into UnifiedState.shadow_state.
It also computes the shadow-vs-live divergence metrics.

The Gap 5 unified ledger handles shadow P&L via the SHADOW book. This bridge handles
shadow PORTFOLIO STATE (positions, not P&L) — what positions does the shadow system
currently hold vs. what the live system holds.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd

from src.core.state_authority import StateAuthority, StateUpdate, WritePriority

logger = logging.getLogger(__name__)


class ShadowStateBridge:
    """Synchronizes shadow trading state into UnifiedState."""
    
    def __init__(
        self,
        shadow_state_path: str,
        state_authority: StateAuthority,
        config: Optional[Dict] = None
    ):
        """
        Initialize the shadow bridge.
        
        Args:
            shadow_state_path: Path to shadow_portfolio_state.parquet
            state_authority: StateAuthority instance for pushing updates
            config: Optional configuration dict
        """
        self.shadow_state_path = Path(shadow_state_path)
        self.state_authority = state_authority
        self.config = config or {}
        
        # Divergence threshold for alerts
        self.divergence_threshold = self.config.get('divergence_threshold', 0.15)
        self.max_shadow_age_days = float(self.config.get('max_shadow_age_days', 7.0))
        self.shadow_positions_path = Path(
            self.config.get('shadow_positions_path', 'data/execution/shadow_positions.parquet')
        )
        
        # Track divergence history for systematic divergence detection
        self.divergence_history = []

        self.state_authority.register_writer(
            writer_id='shadow_bridge',
            allowed_sections=['shadow_state'],
            priority=WritePriority.BRIDGE_SYNC,
        )
        
        logger.info("ShadowStateBridge initialized")
    
    def push_shadow_state(self) -> None:
        """
        Read shadow_portfolio_state.parquet and push summary to UnifiedState.
        
        Computes divergence metrics between shadow and live portfolios.
        """
        try:
            # Check if shadow state file exists
            if not self.shadow_state_path.exists():
                logger.warning(f"Shadow state file not found: {self.shadow_state_path}")
                return
            
            # Read shadow portfolio state
            shadow_df = pd.read_parquet(self.shadow_state_path)
            
            if shadow_df.empty:
                logger.warning("Shadow portfolio state is empty")
                return
            
            # Get most recent shadow state
            latest_shadow = shadow_df.iloc[-1]
            shadow_snapshot_timestamp = self._extract_timestamp(latest_shadow)
            shadow_data_age_days = 0.0
            if shadow_snapshot_timestamp is not None:
                shadow_data_age_days = max(
                    (datetime.now() - shadow_snapshot_timestamp).total_seconds() / 86400.0,
                    0.0,
                )
            shadow_data_stale = bool(
                shadow_snapshot_timestamp is not None
                and shadow_data_age_days > self.max_shadow_age_days
            )
            
            # Extract shadow positions
            shadow_positions = {}
            shadow_equity_deployed = 0.0
            shadow_nav = float(latest_shadow.get('nav', latest_shadow.get('shadow_nav', 0.0)) or 0.0)
            comparison_available = False
            comparison_mode = "none"
            execution_mode = str(latest_shadow.get('execution_mode', 'unknown') or 'unknown')
            tracking_status = str(latest_shadow.get('tracking_status', 'unknown') or 'unknown')
            tracking_breach = bool(latest_shadow.get('tracking_breach', False))
            target_total_weight_drift = float(latest_shadow.get('target_total_weight_drift', 0.0) or 0.0)
            target_max_weight_drift = float(latest_shadow.get('target_max_weight_drift', 0.0) or 0.0)
            target_quantity_mismatch_count = int(latest_shadow.get('target_quantity_mismatch_count', 0) or 0)
            exact_target_match = bool(latest_shadow.get('exact_target_match', False))
            
            # Parse positions if available
            if 'positions' in latest_shadow:
                positions_data = latest_shadow['positions']
                if isinstance(positions_data, dict):
                    shadow_positions = positions_data
                    shadow_equity_deployed = sum(
                        pos.get('market_value', 0.0)
                        for pos in positions_data.values()
                    )
                    comparison_available = True
                    comparison_mode = "positions"
            if not shadow_positions:
                shadow_positions = self._load_shadow_positions_snapshot()
                if shadow_positions:
                    shadow_equity_deployed = sum(
                        float((pos or {}).get('market_value', 0.0) or 0.0)
                        for pos in shadow_positions.values()
                    )
                    comparison_available = True
                    comparison_mode = "positions"
            if shadow_equity_deployed <= 0.0:
                shadow_equity_deployed = float(latest_shadow.get('total_exposure', 0.0) or 0.0)
                if shadow_equity_deployed > 0.0:
                    comparison_mode = "summary_exposure"
            
            # Get live and target equity books from UnifiedState for divergence calculation
            # Note: This requires reading from UnifiedState, which is safe
            live_positions = self._filter_equity_positions(
                self.state_authority.state.portfolio.positions or {}
            )
            target_positions = self._resolve_target_positions(latest_shadow)
            live_nav = self.state_authority.state.portfolio.total_value or 0.0
            target_position_overlap = 1.0
            shadow_extra_positions_count = 0
            shadow_missing_target_positions_count = 0
            target_snapshot_date = ""
            
            # Compute divergence metrics
            if shadow_data_stale:
                logger.warning(
                    "Shadow snapshot is stale (age_days=%.1f > %.1f); suppressing live-shadow divergence alert",
                    shadow_data_age_days,
                    self.max_shadow_age_days,
                )
                position_overlap = 1.0
                target_position_overlap = 1.0
                nav_divergence_pct = 0.0
                comparison_available = False
                comparison_mode = "stale"
            elif comparison_available:
                position_overlap = self.compute_position_overlap(live_positions, shadow_positions)
                target_position_overlap = self.compute_position_overlap(target_positions, shadow_positions)
                target_snapshot_date = self._extract_target_snapshot_date(latest_shadow)
                shadow_set = set(shadow_positions.keys())
                target_set = set(target_positions.keys())
                shadow_extra_positions_count = len(shadow_set - target_set)
                shadow_missing_target_positions_count = len(target_set - shadow_set)
                nav_divergence_pct = self.compute_nav_divergence(live_nav, shadow_nav) if shadow_nav > 0 else 0.0
            else:
                live_exposure = (
                    float(self.state_authority.state.portfolio.invested_value or 0.0) / max(float(live_nav), 1e-9)
                    if live_nav
                    else 0.0
                )
                shadow_exposure = float(latest_shadow.get('total_exposure', 0.0) or 0.0)
                position_overlap = (
                    min(live_exposure, shadow_exposure) / max(live_exposure, shadow_exposure, 1e-9)
                    if live_exposure > 0 and shadow_exposure > 0
                    else 1.0
                )
                target_position_overlap = position_overlap
                shadow_extra_positions_count = 0
                shadow_missing_target_positions_count = 0
                nav_divergence_pct = 0.0
            
            # Check if divergence exceeds threshold
            divergence_alert = bool(comparison_available and abs(nav_divergence_pct) > self.divergence_threshold)
            
            # Track divergence history
            self.divergence_history.append({
                'timestamp': datetime.now(),
                'nav_divergence_pct': nav_divergence_pct,
                'position_overlap': position_overlap
            })
            
            # Keep only last 10 days of history
            if len(self.divergence_history) > 10:
                self.divergence_history = self.divergence_history[-10:]
            
            # Build updates
            updates = [
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_positions',
                    new_value=shadow_positions,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_equity_deployed',
                    new_value=float(shadow_equity_deployed),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_nav',
                    new_value=float(shadow_nav),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='live_shadow_position_overlap',
                    new_value=position_overlap,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='target_shadow_position_overlap',
                    new_value=target_position_overlap,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_extra_positions_count',
                    new_value=int(shadow_extra_positions_count),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_missing_target_positions_count',
                    new_value=int(shadow_missing_target_positions_count),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='target_snapshot_date',
                    new_value=str(target_snapshot_date or ""),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='live_shadow_nav_divergence_pct',
                    new_value=nav_divergence_pct,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='divergence_alert',
                    new_value=divergence_alert,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='comparison_available',
                    new_value=comparison_available,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='comparison_mode',
                    new_value=str(comparison_mode),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='execution_mode',
                    new_value=str(execution_mode),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='tracking_status',
                    new_value=str(tracking_status),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='tracking_breach',
                    new_value=bool(tracking_breach),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='target_total_weight_drift',
                    new_value=float(target_total_weight_drift),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='target_max_weight_drift',
                    new_value=float(target_max_weight_drift),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='target_quantity_mismatch_count',
                    new_value=int(target_quantity_mismatch_count),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='exact_target_match',
                    new_value=bool(exact_target_match),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_snapshot_timestamp',
                    new_value=shadow_snapshot_timestamp,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_data_stale',
                    new_value=shadow_data_stale,
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='shadow_data_age_days',
                    new_value=float(shadow_data_age_days),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
                StateUpdate(
                    writer_id='shadow_bridge',
                    section='shadow_state',
                    field_path='last_sync',
                    new_value=datetime.now(),
                    priority=WritePriority.BRIDGE_SYNC,
                    source='BRIDGE',
                    reason='Shadow state sync'
                ),
            ]
            
            # Apply batch update
            applied = self.state_authority.batch_update(updates)
            logger.info(
                f"Shadow state sync: {applied}/{len(updates)} fields synced, "
                f"NAV divergence: {nav_divergence_pct:.2%}"
            )
            
            if divergence_alert:
                logger.warning(
                    f"Shadow-live divergence alert: {nav_divergence_pct:.2%} "
                    f"exceeds threshold {self.divergence_threshold:.2%}"
                )
            
        except Exception as e:
            logger.error(f"Failed to push shadow state: {e}", exc_info=True)

    def _load_shadow_positions_snapshot(self) -> Dict[str, Any]:
        if not self.shadow_positions_path.exists():
            return {}
        try:
            shadow_positions_df = pd.read_parquet(self.shadow_positions_path)
        except Exception as exc:
            logger.warning("Failed to read shadow positions snapshot: %s", exc)
            return {}
        if shadow_positions_df.empty or 'ticker' not in shadow_positions_df.columns:
            return {}

        if 'date' in shadow_positions_df.columns:
            dates = pd.to_datetime(shadow_positions_df['date'], errors='coerce')
            latest_date = dates.max()
            if pd.notna(latest_date):
                latest_python = pd.Timestamp(latest_date).to_pydatetime()
                if (datetime.now() - latest_python).total_seconds() / 86400.0 > self.max_shadow_age_days:
                    return {}
                shadow_positions_df = shadow_positions_df.loc[dates == latest_date].copy()
        else:
            timestamp_col = next((col for col in ['timestamp', 'updated_at'] if col in shadow_positions_df.columns), None)
            if timestamp_col:
                timestamps = pd.to_datetime(shadow_positions_df[timestamp_col], errors='coerce')
                latest_timestamp = timestamps.max()
                if pd.notna(latest_timestamp):
                    latest_python = pd.Timestamp(latest_timestamp).to_pydatetime()
                    if (datetime.now() - latest_python).total_seconds() / 86400.0 > self.max_shadow_age_days:
                        return {}
                    latest_minute = pd.Timestamp(latest_timestamp).floor('min')
                    shadow_positions_df = shadow_positions_df.loc[
                        timestamps.dt.floor('min') == latest_minute
                    ].copy()

        positions: Dict[str, Any] = {}
        for row in shadow_positions_df.to_dict('records'):
            ticker = str(row.get('ticker') or row.get('symbol') or '').strip()
            if not ticker:
                continue
            positions[ticker] = {
                'shares': float(row.get('shares') or row.get('quantity') or 0.0),
                'avg_price': float(row.get('avg_price') or 0.0),
                'market_value': float(row.get('market_value') or 0.0),
                'unrealized_pnl': float(row.get('unrealized_pnl') or 0.0),
            }
        return positions

    @staticmethod
    def _extract_timestamp(row: pd.Series) -> Optional[datetime]:
        for field_name in ['timestamp', 'updated_at', 'date']:
            parsed = pd.to_datetime(row.get(field_name), errors='coerce')
            if pd.notna(parsed):
                if getattr(parsed, 'tzinfo', None) is not None:
                    parsed = parsed.tz_convert("UTC").tz_localize(None)
                return parsed.to_pydatetime()
        return None
    
    def compute_position_overlap(
        self,
        live_positions: Dict,
        shadow_positions: Dict
    ) -> float:
        """
        Compute position overlap between live and shadow portfolios.
        
        Uses Jaccard similarity on ticker sets weighted by position sizes.
        
        Args:
            live_positions: Live portfolio positions dict
            shadow_positions: Shadow portfolio positions dict
            
        Returns:
            Overlap score from 0.0 (no overlap) to 1.0 (identical)
        """
        if not live_positions and not shadow_positions:
            return 1.0  # Both empty = perfect overlap
        
        if not live_positions or not shadow_positions:
            return 0.0  # One empty = no overlap
        
        # Get ticker sets
        live_tickers = set(live_positions.keys())
        shadow_tickers = set(shadow_positions.keys())
        
        # Jaccard similarity
        intersection = live_tickers & shadow_tickers
        union = live_tickers | shadow_tickers
        
        if not union:
            return 1.0
        
        overlap = len(intersection) / len(union)
        return overlap

    @staticmethod
    def _filter_equity_positions(positions: Dict[str, Any]) -> Dict[str, Any]:
        filtered: Dict[str, Any] = {}
        for symbol, payload in dict(positions or {}).items():
            symbol_text = str(symbol or "").strip()
            if not symbol_text or symbol_text.startswith("OPT::"):
                continue
            payload_dict = payload if isinstance(payload, dict) else {}
            instrument_type = str(payload_dict.get("instrument_type", "equity") or "equity").lower()
            if instrument_type in {"option", "options", "future", "futures", "derivative", "derivatives"}:
                continue
            filtered[symbol_text] = payload_dict
        return filtered

    @staticmethod
    def _filter_target_positions(positions: Dict[str, Any]) -> Dict[str, Any]:
        filtered = ShadowStateBridge._filter_equity_positions(positions)
        pruned: Dict[str, Any] = {}
        for symbol, payload in filtered.items():
            payload_dict = dict(payload or {})
            has_size_fields = any(
                key in payload_dict for key in ("quantity", "notional", "market_value")
            )
            quantity = float(payload_dict.get("quantity", 0.0) or 0.0)
            notional = float(
                payload_dict.get(
                    "notional",
                    payload_dict.get("market_value", 0.0),
                )
                or 0.0
            )
            if has_size_fields and abs(quantity) <= 1e-12 and abs(notional) <= 1e-9:
                continue
            pruned[symbol] = payload_dict
        return pruned

    def _resolve_target_positions(self, latest_shadow: pd.Series) -> Dict[str, Any]:
        target_positions_json = latest_shadow.get("target_positions_json")
        if isinstance(target_positions_json, str) and target_positions_json.strip():
            try:
                payload = json.loads(target_positions_json)
                if isinstance(payload, dict):
                    return self._filter_target_positions(payload)
            except Exception:
                logger.warning("Failed to parse target_positions_json from shadow state")
        return self._filter_target_positions(
            self.state_authority.state.portfolio.target_positions or {}
        )

    @staticmethod
    def _extract_target_snapshot_date(latest_shadow: pd.Series) -> str:
        value = latest_shadow.get("target_snapshot_date")
        return str(value) if value is not None else ""
    
    def compute_nav_divergence(self, live_nav: float, shadow_nav: float) -> float:
        """
        Compute NAV divergence percentage.
        
        Args:
            live_nav: Live portfolio NAV
            shadow_nav: Shadow portfolio NAV
            
        Returns:
            Divergence as percentage: (live_nav - shadow_nav) / live_nav
        """
        if live_nav == 0:
            return 0.0
        
        divergence_pct = (live_nav - shadow_nav) / live_nav
        return divergence_pct
    
    def detect_systematic_divergence(self) -> Optional[str]:
        """
        Check if the live-shadow divergence has been increasing monotonically
        over the past 5 trading days.
        
        Returns:
            Diagnostic string if systematic divergence detected, None otherwise
        """
        if len(self.divergence_history) < 5:
            return None
        
        # Get last 5 divergence values
        recent_divergences = [
            abs(h['nav_divergence_pct'])
            for h in self.divergence_history[-5:]
        ]
        
        # Check if monotonically increasing
        is_increasing = all(
            recent_divergences[i] < recent_divergences[i + 1]
            for i in range(len(recent_divergences) - 1)
        )
        
        if is_increasing:
            return (
                f"Systematic divergence detected: NAV divergence has increased "
                f"monotonically over 5 days from {recent_divergences[0]:.2%} to "
                f"{recent_divergences[-1]:.2%}. This indicates the shadow system "
                f"may not be tracking live system decisions correctly."
            )
        
        return None
