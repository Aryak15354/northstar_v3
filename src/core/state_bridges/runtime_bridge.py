"""
Runtime Bridge — Synchronizes portfolio_runtime.db with UnifiedState and JSON checkpoint.

This bridge ensures the three representations of live equity positions stay consistent:
1. UnifiedState.portfolio_state (in-memory Python)
2. data/portfolio/current_positions.json (JSON file checkpoint)
3. data/runtime/portfolio_runtime.db (SQLite, positions table)
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..state_authority import StateAuthority, StateUpdate, WritePriority

logger = logging.getLogger(__name__)


def _normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        symbol = symbol.rsplit(".", 1)[0]
    if ":" in symbol:
        symbol = symbol.split(":")[-1]
    return symbol


@dataclass
class SyncResult:
    """Result of a bridge sync operation."""
    success: bool
    positions_synced: int
    discrepancies: List[str]
    timestamp: datetime


@dataclass
class InconsistencyReport:
    """Report of inconsistencies between state representations."""
    db_positions: Dict[str, Any]
    unified_positions: Dict[str, Any]
    json_positions: Dict[str, Any]
    discrepancies: List[dict]
    severity: str  # 'INFO', 'WARNING', 'CRITICAL'


class RuntimeStateBridge:
    """
    Synchronizes portfolio runtime database with UnifiedState and JSON checkpoint.
    
    Authority hierarchy for conflict resolution:
    - portfolio_runtime.db is the TRANSACTIONAL authority for individual trades
    - UnifiedState.portfolio_state is the OPERATIONAL authority for running system
    - current_positions.json is the RECOVERY authority for system restarts
    """
    
    def __init__(
        self,
        db_path: str,
        state_authority: StateAuthority,
        config: Optional[dict] = None,
        json_path: Optional[str] = None,
    ):
        """
        Initialize the Runtime Bridge.
        
        Args:
            db_path: Path to portfolio_runtime.db
            state_authority: State authority for updates
            config: System configuration
        """
        self.db_path = Path(db_path)
        self.state_authority = state_authority
        self.config = config or {}
        
        self.json_path = Path(json_path or 'data/portfolio/current_positions.json')
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.materialized_positions_path = Path(
            self.config.get(
                'materialized_positions_path',
                'data/processed/runtime/portfolio_positions_current.parquet',
            )
        )
        
        # Register as a writer
        self.state_authority.register_writer(
            writer_id='runtime_bridge',
            allowed_sections=['portfolio'],
            priority=WritePriority.BRIDGE_SYNC
        )
        
        logger.info(f"RuntimeStateBridge initialized with db: {self.db_path}")
    
    def sync_to_unified_state(self) -> SyncResult:
        """
        Sync portfolio_runtime.db to UnifiedState.portfolio_state.
        
        Returns:
            SyncResult with sync status
        """
        discrepancies = []
        
        try:
            # Read positions from database
            db_positions = self._read_db_positions()
            
            # Read current UnifiedState positions
            unified_positions = self._read_unified_positions()
            
            # Compare and identify discrepancies
            discrepancies = self._compare_positions(db_positions, unified_positions)
            
            if discrepancies:
                logger.warning(f"Found {len(discrepancies)} position discrepancies during sync")
            
            # Push database positions to UnifiedState (db is transactional authority)
            self._push_positions_to_unified(db_positions)
            
            # Compute aggregate metrics
            total_deployed = sum(pos.get('market_value', 0) for pos in db_positions.values())
            position_count = len(db_positions)
            
            # Push aggregates
            self.state_authority.update(StateUpdate(
                writer_id='runtime_bridge',
                section='portfolio',
                field_path='invested_value',
                new_value=total_deployed,
                priority=WritePriority.BRIDGE_SYNC,
                source='BRIDGE',
                reason='Runtime sync'
            ))
            
            self.state_authority.update(StateUpdate(
                writer_id='runtime_bridge',
                section='portfolio',
                field_path='position_count',
                new_value=position_count,
                priority=WritePriority.BRIDGE_SYNC,
                source='BRIDGE',
                reason='Runtime sync'
            ))

            self.state_authority.update(StateUpdate(
                writer_id='runtime_bridge',
                section='portfolio',
                field_path='total_positions',
                new_value=position_count,
                priority=WritePriority.BRIDGE_SYNC,
                source='BRIDGE',
                reason='Runtime sync'
            ))
            
            logger.info(f"Synced {position_count} positions to UnifiedState")
            
            return SyncResult(
                success=True,
                positions_synced=position_count,
                discrepancies=discrepancies,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to sync to UnifiedState: {e}")
            return SyncResult(
                success=False,
                positions_synced=0,
                discrepancies=[str(e)],
                timestamp=datetime.now()
            )
    
    def sync_to_json_checkpoint(self) -> None:
        """
        Write current_positions.json from UnifiedState.portfolio_state.
        
        Called every 60 seconds and after every position change.
        """
        try:
            # Read from UnifiedState
            unified_positions = self._read_unified_positions()
            existing_payload = self._read_json_payload()
            positions_payload = self._merge_positions(existing_payload.get('positions', {}), unified_positions)
            invested_value = float(
                sum(float((payload or {}).get('market_value', 0.0) or 0.0) for payload in positions_payload.values())
            )

            checkpoint_data = dict(existing_payload)
            checkpoint_data.update(
                {
                    'timestamp': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                    'position_count': len(positions_payload),
                    'invested_value': invested_value,
                    'positions': positions_payload,
                }
            )
            
            # Atomic write (write to temp, then rename)
            temp_path = self.json_path.with_suffix('.json.tmp')
            with open(temp_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
            
            temp_path.rename(self.json_path)
            
            logger.debug(f"Wrote JSON checkpoint with {len(unified_positions)} positions")
            
        except Exception as e:
            logger.error(f"Failed to write JSON checkpoint: {e}")

    def _read_json_payload(self) -> Dict[str, Any]:
        if not self.json_path.exists():
            return {}
        try:
            with open(self.json_path, 'r') as f:
                payload = json.load(f)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _merge_positions(self, existing_positions: Dict[str, Any], latest_positions: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        existing_normalized = {
            _normalize_symbol(symbol): dict(payload)
            for symbol, payload in (existing_positions or {}).items()
            if isinstance(payload, dict)
        }
        for symbol, payload in (latest_positions or {}).items():
            row = dict(existing_normalized.get(_normalize_symbol(symbol), {}))
            row.update(dict(payload or {}))
            merged[str(symbol)] = row
        return merged
    
    def detect_triplet_inconsistency(self) -> Optional[InconsistencyReport]:
        """
        Compare all three representations and detect inconsistencies.
        
        Returns:
            InconsistencyReport if inconsistencies found, None if all agree
        """
        try:
            # Read from all three sources
            db_positions = self._read_db_positions()
            unified_positions = self._read_unified_positions()
            json_positions = self._read_json_positions()
            
            # Compare all three
            discrepancies = []
            
            all_tickers = set(db_positions.keys()) | set(unified_positions.keys()) | set(json_positions.keys())
            
            for ticker in all_tickers:
                db_qty = db_positions.get(ticker, {}).get('quantity', 0)
                unified_qty = unified_positions.get(ticker, {}).get('quantity', 0)
                json_qty = json_positions.get(ticker, {}).get('quantity', 0)
                
                # Check for presence/absence
                in_db = ticker in db_positions
                in_unified = ticker in unified_positions
                in_json = ticker in json_positions
                
                if not (in_db and in_unified and in_json):
                    discrepancies.append({
                        'ticker': ticker,
                        'type': 'MISSING_POSITION',
                        'in_db': in_db,
                        'in_unified': in_unified,
                        'in_json': in_json,
                        'severity': 'CRITICAL' if in_db and not in_unified else 'WARNING'
                    })
                    continue
                
                # Check for quantity differences
                qty_diff_db_unified = abs(db_qty - unified_qty)
                qty_diff_db_json = abs(db_qty - json_qty)
                
                if qty_diff_db_unified > 1:  # More than 1 share difference
                    discrepancies.append({
                        'ticker': ticker,
                        'type': 'QUANTITY_MISMATCH',
                        'db_quantity': db_qty,
                        'unified_quantity': unified_qty,
                        'json_quantity': json_qty,
                        'severity': 'CRITICAL' if qty_diff_db_unified > db_qty * 0.05 else 'WARNING'
                    })
                
                if qty_diff_db_json > 1:
                    discrepancies.append({
                        'ticker': ticker,
                        'type': 'JSON_MISMATCH',
                        'db_quantity': db_qty,
                        'json_quantity': json_qty,
                        'severity': 'WARNING'
                    })
            
            if not discrepancies:
                return None
            
            # Determine overall severity
            has_critical = any(d.get('severity') == 'CRITICAL' for d in discrepancies)
            severity = 'CRITICAL' if has_critical else 'WARNING'
            
            return InconsistencyReport(
                db_positions=db_positions,
                unified_positions=unified_positions,
                json_positions=json_positions,
                discrepancies=discrepancies,
                severity=severity
            )
            
        except Exception as e:
            logger.error(f"Failed to detect inconsistencies: {e}")
            return None
    
    def reconcile_on_startup(self) -> dict:
        """
        Reconcile all three sources on system startup.
        
        Returns:
            Reconciliation result with authoritative state
        """
        logger.info("Running startup reconciliation...")
        
        try:
            # Read from all sources
            db_positions = self._read_db_positions()
            unified_positions = self._read_unified_positions()
            json_positions = self._read_json_positions()
            
            reconciliation = {
                'timestamp': datetime.now().isoformat(),
                'db_position_count': len(db_positions),
                'unified_position_count': len(unified_positions),
                'json_position_count': len(json_positions),
                'conflicts': [],
                'authoritative_source': 'database',
                'action_taken': 'none',
            }
            
            # Use database as authoritative source for individual positions
            # (it has the transactional trade history)
            authoritative_positions = db_positions
            
            # Check for major conflicts
            if len(db_positions) != len(unified_positions):
                reconciliation['conflicts'].append({
                    'type': 'POSITION_COUNT_MISMATCH',
                    'db_count': len(db_positions),
                    'unified_count': len(unified_positions),
                    'resolution': 'Using database count'
                })
                reconciliation['action_taken'] = 'sync_to_unified'
            
            # Sync UnifiedState to match database
            if reconciliation['action_taken'] == 'sync_to_unified':
                self._push_positions_to_unified(authoritative_positions)
                logger.info(f"Reconciled UnifiedState to match database: {len(authoritative_positions)} positions")
            
            return reconciliation
            
        except Exception as e:
            logger.error(f"Startup reconciliation failed: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'authoritative_source': 'unknown',
            }
    
    def _read_db_positions(self) -> Dict[str, Any]:
        """Read positions from portfolio_runtime.db."""
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
            return self._read_materialized_positions()
        
        positions = {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Try to read from positions table
            cursor.execute("""
                SELECT ticker, quantity, avg_price, market_value, last_updated
                FROM positions
                WHERE quantity != 0
            """)
            
            for row in cursor.fetchall():
                ticker, quantity, avg_price, market_value, last_updated = row
                positions[ticker] = {
                    'quantity': quantity,
                    'avg_price': avg_price,
                    'market_value': market_value,
                    'last_updated': last_updated,
                }

            conn.close()
            if positions:
                return positions
            return self._read_materialized_positions()
            
        except sqlite3.OperationalError as e:
            if 'no such table' in str(e).lower():
                logger.info(
                    "Positions table not found in runtime DB %s; using materialized runtime view if available",
                    self.db_path,
                )
                return self._read_materialized_positions()
            logger.error(f"Failed to read positions from database: {e}")
        except Exception as e:
            logger.error(f"Failed to read positions from database: {e}")

        if positions:
            return positions
        return self._read_materialized_positions()

    def _read_materialized_positions(self) -> Dict[str, Any]:
        """Fallback reader for PRS materialized positions parquet."""
        if not self.materialized_positions_path.exists():
            return {}

        try:
            df = pd.read_parquet(self.materialized_positions_path)
        except Exception as e:
            logger.warning("Failed to read materialized runtime positions: %s", e)
            return {}

        if df.empty:
            return {}

        symbol_col = next((col for col in ['symbol', 'ticker', 'underlying'] if col in df.columns), None)
        if symbol_col is None:
            return {}

        quantity_col = next(
            (col for col in ['quantity', 'qty', 'position_qty', 'net_quantity'] if col in df.columns),
            None,
        )
        avg_price_col = next((col for col in ['avg_price', 'average_price', 'entry_price'] if col in df.columns), None)
        market_value_col = next(
            (col for col in ['market_value', 'notional', 'current_value', 'position_value'] if col in df.columns),
            None,
        )
        updated_col = next(
            (col for col in ['last_updated', 'updated_at', 'timestamp', 'timestamp_utc'] if col in df.columns),
            None,
        )

        positions: Dict[str, Any] = {}
        for row in df.to_dict('records'):
            symbol = str(row.get(symbol_col) or '').strip()
            if not symbol:
                continue
            quantity = row.get(quantity_col, 0.0) if quantity_col else 0.0
            try:
                quantity = float(quantity or 0.0)
            except Exception:
                quantity = 0.0
            if abs(quantity) <= 1e-12 and quantity_col:
                continue
            positions[symbol] = {
                'quantity': quantity,
                'avg_price': float(row.get(avg_price_col) or 0.0) if avg_price_col else 0.0,
                'market_value': float(row.get(market_value_col) or 0.0) if market_value_col else 0.0,
                'last_updated': row.get(updated_col) if updated_col else None,
                'instrument_type': row.get('instrument_type'),
                'sector': row.get('sector'),
                'strategy_id': row.get('strategy_id'),
                'origin': row.get('origin'),
            }

        return positions
    
    def _read_unified_positions(self) -> Dict[str, Any]:
        """Read positions from UnifiedState.portfolio_state."""
        try:
            return dict(self.state_authority.state.portfolio.positions or {})
        except Exception as e:
            logger.error(f"Failed to read UnifiedState positions: {e}")
            return {}
    
    def _read_json_positions(self) -> Dict[str, Any]:
        """Read positions from current_positions.json."""
        if not self.json_path.exists():
            return {}
        
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
                return data.get('positions', {})
        except Exception as e:
            logger.error(f"Failed to read JSON checkpoint: {e}")
            return {}
    
    def _compare_positions(self, db_positions: Dict, unified_positions: Dict) -> List[str]:
        """Compare two position dictionaries and return discrepancies."""
        if self._looks_like_target_book(unified_positions):
            return [
                "unified portfolio contains target-weight rows rather than live quantities; runtime bridge will reconcile"
            ]

        discrepancies = []
        normalized_db = {
            _normalize_symbol(ticker): payload
            for ticker, payload in db_positions.items()
            if _normalize_symbol(ticker)
        }
        normalized_unified = {
            _normalize_symbol(ticker): payload
            for ticker, payload in unified_positions.items()
            if _normalize_symbol(ticker)
        }

        all_tickers = set(normalized_db.keys()) | set(normalized_unified.keys())

        for ticker in all_tickers:
            db_qty = self._extract_quantity(normalized_db.get(ticker, {}))
            unified_qty = self._extract_quantity(normalized_unified.get(ticker, {}))

            if abs(db_qty - unified_qty) > 1:
                discrepancies.append(f"{ticker}: db={db_qty}, unified={unified_qty}")

        return discrepancies

    @staticmethod
    def _extract_quantity(position: Dict[str, Any]) -> float:
        if not isinstance(position, dict):
            return 0.0
        for key in ['quantity', 'qty', 'shares', 'position_qty', 'net_quantity']:
            try:
                return float(position.get(key) or 0.0)
            except Exception:
                continue
        return 0.0

    @staticmethod
    def _looks_like_target_book(positions: Dict[str, Any]) -> bool:
        if not positions:
            return False
        rows = [payload for payload in positions.values() if isinstance(payload, dict)]
        if not rows:
            return False
        missing_quantity = 0
        target_like = 0
        for payload in rows:
            if not any(key in payload for key in ['quantity', 'qty', 'shares', 'position_qty', 'net_quantity']):
                missing_quantity += 1
            if any(key in payload for key in ['weight', 'final_weight', 'exposure', 'selection_score']):
                target_like += 1
        return missing_quantity >= max(1, int(len(rows) * 0.7)) and target_like >= max(1, int(len(rows) * 0.5))
    
    def _push_positions_to_unified(self, positions: Dict[str, Any]) -> None:
        """Push positions to UnifiedState via StateAuthority."""
        self.state_authority.update(StateUpdate(
            writer_id='runtime_bridge',
            section='portfolio',
            field_path='positions',
            new_value=positions,
            priority=WritePriority.BRIDGE_SYNC,
            source='BRIDGE',
            reason='Runtime sync'
        ))
