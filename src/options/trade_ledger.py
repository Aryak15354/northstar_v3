"""
Immutable Trade Ledger for Options Trading

Append-only parquet storage for complete audit trail of all trades.
Once written, records are never modified - only new records appended.

Philosophy: Immutability enables trust - every decision is permanently recorded.
"""

import logging
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.options.position_manager import Position, PositionLeg, Greeks
from src.options.tax_aware_pnl_tracker import TradePnL
from src.options.state_io import WriteAheadLog

logger = logging.getLogger("options.trade_ledger")
GENERIC_UNDERLYING_TOKENS = {"NSE", "NSE_EQ", "NSE_FO", "NSE_INDEX", "NFO", "BSE", "BSE_EQ", "BSE_FO"}
_TRADE_ID_TS_RE = re.compile(r"^POS_(\d{8})_(\d{6})_")


@dataclass
class LedgerEntry:
    """Single entry in the trade ledger"""
    trade_id: str
    timestamp: datetime
    action: str  # 'open' or 'close'
    strategy_type: str
    regime_at_entry: str
    underlying: str
    expiry: datetime
    legs: str  # JSON serialized list of legs
    entry_credit_debit: float
    max_loss: Optional[float]
    max_profit: Optional[float]
    exit_value: Optional[float]
    gross_pnl: Optional[float]
    costs: Optional[float]
    tax: Optional[float]
    net_pnl: Optional[float]
    days_held: int
    exit_reason: Optional[str]
    greeks_at_entry: str  # JSON serialized Greeks
    greeks_at_exit: Optional[str]  # JSON serialized Greeks


class TradeLedger:
    """
    Immutable trade ledger with append-only writes.
    
    Responsibilities:
    - Write trade records on position open and close
    - Never modify existing records
    - Provide read access for audit and analysis
    - Ensure data integrity and immutability
    
    Storage Format: Parquet (columnar, compressed, efficient)
    Write Pattern: Append-only (no updates or deletes)
    """
    
    # Parquet schema definition
    SCHEMA = pa.schema([
        ('trade_id', pa.string()),
        ('timestamp', pa.timestamp('ns')),
        ('action', pa.string()),
        ('strategy_type', pa.string()),
        ('regime_at_entry', pa.string()),
        ('underlying', pa.string()),
        ('expiry', pa.timestamp('ns')),
        ('legs', pa.string()),  # JSON
        ('entry_credit_debit', pa.float64()),
        ('max_loss', pa.float64()),
        ('max_profit', pa.float64()),
        ('exit_value', pa.float64()),
        ('gross_pnl', pa.float64()),
        ('costs', pa.float64()),
        ('tax', pa.float64()),
        ('net_pnl', pa.float64()),
        ('days_held', pa.int32()),
        ('exit_reason', pa.string()),
        ('greeks_at_entry', pa.string()),  # JSON
        ('greeks_at_exit', pa.string()),  # JSON
    ])
    
    def __init__(self, ledger_path: str):
        """
        Initialize trade ledger
        
        Args:
            ledger_path: Path to parquet file
        """
        self.ledger_path = Path(ledger_path)
        self._wal = WriteAheadLog(self._default_wal_path())
        self._live_options_dir = self.ledger_path.parent / "live"
        self._instrument_underlying_cache: Dict[str, str] = {}
        self._cache_refreshed_at: Optional[datetime] = None
        self._cache_ttl_seconds = 300
        
        # Ensure directory exists
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize empty ledger if doesn't exist
        if not self.ledger_path.exists():
            self._initialize_empty_ledger()
            logger.info(f"Initialized empty trade ledger at {self.ledger_path}")
        else:
            logger.info(f"Using existing trade ledger at {self.ledger_path}")

    def _default_wal_path(self) -> Path:
        """
        Keep the ledger WAL in a shared runtime area rather than next to ad hoc
        ledger paths so temporary/test ledgers do not leave sidecar directories
        behind after cleanup.
        """
        runtime_dir = Path.cwd() / "data" / "runtime" / "options_trade_ledger"
        return runtime_dir / f"{self.ledger_path.stem}_write_journal.log"

    @staticmethod
    def _normalize_underlying(value: Any) -> str:
        text = str(value or "").strip().upper()
        exchange_prefixes = {"NSE_FO", "NSE_EQ", "NSE_INDEX", "BSE_FO", "BSE_EQ"}
        if "|" in text:
            left, right = text.split("|", 1)
            left = left.strip().upper()
            right = right.strip().upper()
            if left in exchange_prefixes:
                if right and (right.replace(" ", "").isalpha() or (" " in right and any(c.isalpha() for c in right))):
                    text = right
                else:
                    text = left
            elif right and right.isalpha():
                text = right
        if ":" in text:
            left, right = text.split(":", 1)
            left = left.strip().upper()
            right = right.strip().upper()
            if left in exchange_prefixes:
                if right and (right.replace(" ", "").isalpha() or (" " in right and any(c.isalpha() for c in right))):
                    text = right
                else:
                    text = left
            elif right and right.isalpha():
                text = right
        if text.endswith(".NS"):
            text = text[:-3]
        alias_map = {
            "NIFTY 50": "NIFTY",
            "NIFTY BANK": "BANKNIFTY",
            "NIFTY FIN SERVICE": "FINNIFTY",
        }
        return alias_map.get(text, text)

    def _refresh_instrument_underlying_cache(self) -> None:
        now = datetime.now()
        if self._cache_refreshed_at is not None:
            age = (now - self._cache_refreshed_at).total_seconds()
            if age < self._cache_ttl_seconds:
                return

        cache: Dict[str, str] = {}
        try:
            for path in sorted(self._live_options_dir.glob("*_options_latest.parquet")):
                try:
                    df = pd.read_parquet(path, columns=["instrument_key", "underlying"])
                except Exception:
                    continue
                if df is None or df.empty:
                    continue
                if "instrument_key" not in df.columns:
                    continue
                fallback_underlying = self._normalize_underlying(path.name.split("_options_latest.parquet", 1)[0])
                underlying_series = (
                    df["underlying"] if "underlying" in df.columns else pd.Series([fallback_underlying] * len(df))
                )
                for ik, ul in zip(df["instrument_key"].astype(str), underlying_series.astype(str)):
                    key = str(ik or "").strip()
                    if not key:
                        continue
                    normalized_underlying = self._normalize_underlying(ul) or fallback_underlying
                    if not normalized_underlying:
                        continue
                    cache[str(key).upper()] = normalized_underlying
                    cache[str(key).replace(":", "|").upper()] = normalized_underlying
                    cache[str(key).replace("|", ":").upper()] = normalized_underlying
        except Exception:
            pass

        self._instrument_underlying_cache = cache
        self._cache_refreshed_at = now

    def _infer_underlying_from_legs(self, legs: List[PositionLeg]) -> str:
        if not legs:
            return ""

        # Fast path: parse symbolic leg names.
        for leg in legs:
            symbol = str(getattr(leg, "symbol", "") or "").strip().upper()
            if not symbol:
                continue
            normalized = self._normalize_underlying(symbol)
            if (
                normalized
                and "|" not in normalized
                and ":" not in normalized
                and normalized not in GENERIC_UNDERLYING_TOKENS
                and not normalized.isdigit()
            ):
                return normalized
            if "_" in symbol:
                token = symbol.split("_", 1)[0].strip().upper()
                if token and token not in GENERIC_UNDERLYING_TOKENS:
                    return token

        # Fallback: map instrument keys from latest option-chain cache.
        self._refresh_instrument_underlying_cache()
        for leg in legs:
            symbol = str(getattr(leg, "symbol", "") or "").strip().upper()
            if not symbol:
                continue
            mapped = self._instrument_underlying_cache.get(symbol)
            if not mapped:
                mapped = self._instrument_underlying_cache.get(symbol.replace(":", "|"))
            if not mapped:
                mapped = self._instrument_underlying_cache.get(symbol.replace("|", ":"))
            if mapped:
                normalized = self._normalize_underlying(mapped)
                if normalized:
                    return normalized
        return ""

    def _canonical_underlying(self, primary: Any, legs: List[PositionLeg]) -> str:
        normalized_primary = self._normalize_underlying(primary)
        if (
            normalized_primary
            and "|" not in normalized_primary
            and ":" not in normalized_primary
            and normalized_primary not in GENERIC_UNDERLYING_TOKENS
            and not normalized_primary.isdigit()
        ):
            return normalized_primary

        inferred = self._infer_underlying_from_legs(legs)
        if inferred:
            return inferred

        if normalized_primary and normalized_primary not in GENERIC_UNDERLYING_TOKENS:
            return normalized_primary
        return "UNKNOWN"
    
    def _initialize_empty_ledger(self) -> None:
        """Create empty parquet file with schema"""
        empty_df = pd.DataFrame({
            'trade_id': pd.Series(dtype='str'),
            'timestamp': pd.Series(dtype='datetime64[ns]'),
            'action': pd.Series(dtype='str'),
            'strategy_type': pd.Series(dtype='str'),
            'regime_at_entry': pd.Series(dtype='str'),
            'underlying': pd.Series(dtype='str'),
            'expiry': pd.Series(dtype='datetime64[ns]'),
            'legs': pd.Series(dtype='str'),
            'entry_credit_debit': pd.Series(dtype='float64'),
            'max_loss': pd.Series(dtype='float64'),
            'max_profit': pd.Series(dtype='float64'),
            'exit_value': pd.Series(dtype='float64'),
            'gross_pnl': pd.Series(dtype='float64'),
            'costs': pd.Series(dtype='float64'),
            'tax': pd.Series(dtype='float64'),
            'net_pnl': pd.Series(dtype='float64'),
            'days_held': pd.Series(dtype='int32'),
            'exit_reason': pd.Series(dtype='str'),
            'greeks_at_entry': pd.Series(dtype='str'),
            'greeks_at_exit': pd.Series(dtype='str'),
        })
        
        # Write empty parquet file
        table = pa.Table.from_pandas(empty_df, schema=self.SCHEMA)
        pq.write_table(table, self.ledger_path)
    
    def _serialize_legs(self, legs: List[PositionLeg]) -> str:
        """Serialize position legs to JSON"""
        legs_data = []
        for leg in legs:
            leg_dict = {
                'symbol': leg.symbol,
                'strike': leg.strike,
                'option_type': leg.option_type,
                'action': leg.action,
                'quantity': leg.quantity,
                'entry_premium': leg.entry_premium,
                'current_premium': leg.current_premium,
                'entry_iv': leg.entry_iv,
                'current_iv': leg.current_iv,
                'delta': leg.delta,
                'gamma': leg.gamma,
                'theta': leg.theta,
                'vega': leg.vega,
            }
            legs_data.append(leg_dict)
        return json.dumps(legs_data)
    
    def _serialize_greeks(self, greeks: Optional[Greeks]) -> Optional[str]:
        """Serialize Greeks to JSON"""
        if greeks is None:
            return None
        
        greeks_dict = {
            'delta': greeks.delta,
            'gamma': greeks.gamma,
            'theta': greeks.theta,
            'vega': greeks.vega,
        }
        return json.dumps(greeks_dict)

    def _serialize_runtime_legs(self, legs: List[Dict[str, Any]]) -> str:
        return json.dumps([dict(leg or {}) for leg in legs])

    def _serialize_runtime_greeks(self, greeks: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(greeks, dict):
            return None
        payload = {
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
        }
        return json.dumps(payload)

    @staticmethod
    def _infer_timestamp_from_trade_id(trade_id: Any) -> Optional[datetime]:
        text = str(trade_id or "").strip().upper()
        match = _TRADE_ID_TS_RE.match(text)
        if not match:
            return None
        date_token = str(match.group(1))
        time_token = str(match.group(2))
        try:
            ts = pd.to_datetime(
                f"{date_token}{time_token}",
                format="%Y%m%d%H%M%S",
                errors="coerce",
            )
            if pd.isna(ts):
                return None
            return ts.to_pydatetime()
        except Exception:
            return None

    def _safe_timestamp(self, value: Any, trade_id: str, field_name: str) -> datetime:
        ts = pd.to_datetime(value, errors="coerce")
        if not pd.isna(ts):
            return ts.to_pydatetime()

        inferred = self._infer_timestamp_from_trade_id(trade_id)
        if inferred is not None:
            logger.warning(
                "Ledger %s timestamp missing for %s; inferred from trade_id",
                field_name,
                trade_id,
            )
            return inferred

        logger.warning(
            "Ledger %s timestamp missing for %s; fallback now() applied",
            field_name,
            trade_id,
        )
        return datetime.now()

    def _entry_exists(self, trade_id: str, action: str) -> bool:
        try:
            df = self.read_by_trade_id(trade_id)
        except Exception:
            return False
        if df.empty or "action" not in df.columns:
            return False
        actions = df["action"].astype(str).str.lower()
        return bool((actions == str(action or "").strip().lower()).any())
    
    def write_position_open(self, position: Position) -> None:
        """
        Write trade record when position is opened
        
        Args:
            position: Newly opened position
        """
        if self._entry_exists(str(position.position_id), "open"):
            logger.debug("Skipping duplicate open ledger entry for %s", position.position_id)
            return

        # Create ledger entry
        underlying = self._canonical_underlying(getattr(position, "underlying", ""), position.legs)
        entry_ts = self._safe_timestamp(getattr(position, "entry_time", None), str(position.position_id), "entry")

        entry = LedgerEntry(
            trade_id=position.position_id,
            timestamp=entry_ts,
            action='open',
            strategy_type=position.strategy_type,
            regime_at_entry=position.regime_at_entry.value,
            underlying=underlying,
            expiry=pd.Timestamp(position.expiry),
            legs=self._serialize_legs(position.legs),
            entry_credit_debit=position.entry_credit_debit,
            max_loss=float(position.max_loss) if position.max_loss is not None else None,
            max_profit=float(position.max_profit) if position.max_profit is not None else None,
            exit_value=None,
            gross_pnl=None,
            costs=None,
            tax=None,
            net_pnl=None,
            days_held=0,
            exit_reason=None,
            greeks_at_entry=self._serialize_greeks(position.entry_greeks),
            greeks_at_exit=None
        )
        
        # Append to ledger
        self._append_entry(entry)
        
        logger.info(f"Wrote position open to ledger: {position.position_id}")
    
    def write_position_close(
        self,
        position: Position,
        trade_pnl: TradePnL
    ) -> None:
        """
        Write trade record when position is closed
        
        Args:
            position: Closed position
            trade_pnl: Complete P&L breakdown
        """
        if position.is_open():
            raise ValueError(f"Cannot write close record for open position {position.position_id}")
        if self._entry_exists(str(position.position_id), "close"):
            logger.debug("Skipping duplicate close ledger entry for %s", position.position_id)
            return
        
        # Create ledger entry
        underlying = self._canonical_underlying(getattr(position, "underlying", ""), position.legs)
        exit_ts = self._safe_timestamp(getattr(position, "exit_time", None), str(position.position_id), "exit")

        entry = LedgerEntry(
            trade_id=position.position_id,
            timestamp=exit_ts,
            action='close',
            strategy_type=position.strategy_type,
            regime_at_entry=position.regime_at_entry.value,
            underlying=underlying,
            expiry=pd.Timestamp(position.expiry),
            legs=self._serialize_legs(position.legs),
            entry_credit_debit=position.entry_credit_debit,
            max_loss=float(position.max_loss) if position.max_loss is not None else None,
            max_profit=float(position.max_profit) if position.max_profit is not None else None,
            exit_value=position.current_value,
            gross_pnl=trade_pnl.gross_pnl,
            costs=trade_pnl.costs.total,
            tax=trade_pnl.tax,
            net_pnl=trade_pnl.net_pnl,
            days_held=position.days_held,
            exit_reason=position.exit_reason,
            greeks_at_entry=self._serialize_greeks(position.entry_greeks),
            greeks_at_exit=self._serialize_greeks(position.greeks)
        )
        
        # Append to ledger
        self._append_entry(entry)
        
        logger.info(
            f"Wrote position close to ledger: {position.position_id}, "
            f"Net P&L: ₹{trade_pnl.net_pnl:,.0f}"
        )

    def sync_runtime_state(self, runtime_state: Dict[str, Any]) -> Dict[str, int]:
        """
        Recovery helper: backfill immutable ledger entries from the canonical
        options runtime snapshot when a prior cycle mutated runtime state before
        the ledger write completed.
        """
        payload = dict(runtime_state or {})
        backfilled = {"open_entries": 0, "close_entries": 0}

        open_positions = payload.get("open_positions", [])
        if isinstance(open_positions, list):
            for row in open_positions:
                if not isinstance(row, dict):
                    continue
                trade_id = str(row.get("position_id") or "").strip()
                if not trade_id or self._entry_exists(trade_id, "open"):
                    continue
                legs = list(row.get("legs") or [])
                entry = LedgerEntry(
                    trade_id=trade_id,
                    timestamp=self._safe_timestamp(row.get("entry_time"), trade_id, "entry"),
                    action="open",
                    strategy_type=str(row.get("strategy_type") or "unknown"),
                    regime_at_entry=str(row.get("regime_at_entry") or "unknown"),
                    underlying=self._canonical_underlying(row.get("underlying"), []),
                    expiry=pd.Timestamp(pd.to_datetime(row.get("expiry"), errors="coerce")),
                    legs=self._serialize_runtime_legs(legs),
                    entry_credit_debit=float(row.get("entry_credit_debit", 0.0) or 0.0),
                    max_loss=float(row.get("max_loss", 0.0) or 0.0) if row.get("max_loss") is not None else None,
                    max_profit=float(row.get("max_profit", 0.0) or 0.0) if row.get("max_profit") is not None else None,
                    exit_value=None,
                    gross_pnl=None,
                    costs=None,
                    tax=None,
                    net_pnl=None,
                    days_held=int(row.get("days_held", 0) or 0),
                    exit_reason=None,
                    greeks_at_entry=self._serialize_runtime_greeks(row.get("entry_greeks")),
                    greeks_at_exit=None,
                )
                self._append_entry(entry)
                backfilled["open_entries"] += 1

        closed_positions = payload.get("closed_positions", [])
        if isinstance(closed_positions, list):
            for row in closed_positions:
                if not isinstance(row, dict):
                    continue
                trade_id = str(row.get("position_id") or "").strip()
                if not trade_id or self._entry_exists(trade_id, "close"):
                    continue
                exit_time = row.get("exit_time")
                if not exit_time:
                    continue
                realized = row.get("realized_pnl")
                net_pnl = float(realized or 0.0)
                legs = list(row.get("legs") or [])
                entry = LedgerEntry(
                    trade_id=trade_id,
                    timestamp=self._safe_timestamp(exit_time, trade_id, "exit"),
                    action="close",
                    strategy_type=str(row.get("strategy_type") or "unknown"),
                    regime_at_entry=str(row.get("regime_at_entry") or "unknown"),
                    underlying=self._canonical_underlying(row.get("underlying"), []),
                    expiry=pd.Timestamp(pd.to_datetime(row.get("expiry"), errors="coerce")),
                    legs=self._serialize_runtime_legs(legs),
                    entry_credit_debit=float(row.get("entry_credit_debit", 0.0) or 0.0),
                    max_loss=float(row.get("max_loss", 0.0) or 0.0) if row.get("max_loss") is not None else None,
                    max_profit=float(row.get("max_profit", 0.0) or 0.0) if row.get("max_profit") is not None else None,
                    exit_value=float(row.get("current_value", 0.0) or 0.0),
                    gross_pnl=net_pnl,
                    costs=0.0,
                    tax=0.0,
                    net_pnl=net_pnl,
                    days_held=int(row.get("days_held", 0) or 0),
                    exit_reason=str(row.get("exit_reason") or ""),
                    greeks_at_entry=self._serialize_runtime_greeks(row.get("entry_greeks")),
                    greeks_at_exit=self._serialize_runtime_greeks(row.get("greeks")),
                )
                self._append_entry(entry)
                backfilled["close_entries"] += 1

        return backfilled
    
    def _append_entry(self, entry: LedgerEntry) -> None:
        """
        Append entry to ledger (immutable operation)
        
        Args:
            entry: Ledger entry to append
        """
        op_id = f"ledger_{entry.action}_{entry.trade_id}_{int(datetime.now().timestamp() * 1_000_000)}"

        # Convert entry to DataFrame
        entry_dict = asdict(entry)
        entry_df = pd.DataFrame([entry_dict])
        tmp_path = self.ledger_path.with_suffix(f"{self.ledger_path.suffix}.tmp")

        checksum_before = self._wal._compute_checksum(self.ledger_path)
        self._wal.log_operation(
            op_id=op_id,
            stage="prepared",
            target_path=self.ledger_path,
            checksum_before=checksum_before,
        )

        try:
            # Read existing ledger
            existing_df = self._ensure_schema_dataframe(pd.read_parquet(self.ledger_path))
            entry_df = self._ensure_schema_dataframe(entry_df)

            # Append new entry
            if existing_df.empty:
                updated_df = entry_df.copy()
            else:
                updated_df = existing_df.copy()
                updated_df.loc[len(updated_df)] = entry_df.iloc[0]

            # Write new ledger file to temp then atomically replace.
            table = pa.Table.from_pandas(updated_df, schema=self.SCHEMA)
            pq.write_table(table, tmp_path)
            tmp_path.replace(self.ledger_path)

            checksum_after = self._wal._compute_checksum(self.ledger_path)
            self._wal.log_operation(
                op_id=op_id,
                stage="committed",
                target_path=self.ledger_path,
                checksum_before=checksum_before,
                checksum_after=checksum_after,
            )
            logger.debug(f"Appended entry to ledger: {entry.trade_id} ({entry.action})")
        except Exception as exc:
            self._wal.log_operation(
                op_id=op_id,
                stage="failed",
                target_path=self.ledger_path,
                checksum_before=checksum_before,
                error=str(exc),
            )
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise

    def _ensure_schema_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Backfill missing columns and align ordering to the canonical schema."""
        aligned = df.copy()
        for col in self.SCHEMA.names:
            if col not in aligned.columns:
                aligned[col] = None
        aligned = aligned[self.SCHEMA.names]
        if "timestamp" in aligned.columns:
            aligned["timestamp"] = pd.to_datetime(aligned["timestamp"], errors="coerce")
        if "expiry" in aligned.columns:
            aligned["expiry"] = pd.to_datetime(aligned["expiry"], errors="coerce")
        if "days_held" in aligned.columns:
            aligned["days_held"] = pd.to_numeric(aligned["days_held"], errors="coerce").fillna(0).astype("int32")
        return aligned
    
    def read_all(self) -> pd.DataFrame:
        """
        Read entire trade ledger
        
        Returns:
            pd.DataFrame: All ledger entries
        """
        return pd.read_parquet(self.ledger_path)
    
    def read_by_trade_id(self, trade_id: str) -> pd.DataFrame:
        """
        Read all entries for a specific trade
        
        Args:
            trade_id: Trade ID to filter by
        
        Returns:
            pd.DataFrame: Entries for the trade (open + close)
        """
        df = self.read_all()
        return df[df['trade_id'] == trade_id]
    
    def read_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Read entries within date range
        
        Args:
            start_date: Start of date range
            end_date: End of date range
        
        Returns:
            pd.DataFrame: Entries within date range
        """
        df = self.read_all()
        mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
        return df[mask]
    
    def read_closed_trades(self) -> pd.DataFrame:
        """
        Read only closed trade entries
        
        Returns:
            pd.DataFrame: Closed trade entries
        """
        df = self.read_all()
        return df[df['action'] == 'close']
    
    def get_trade_count(self) -> int:
        """Get total number of trades (open + close entries)"""
        df = self.read_all()
        return len(df)
    
    def get_closed_trade_count(self) -> int:
        """Get number of closed trades"""
        df = self.read_closed_trades()
        return len(df)
    
    def verify_immutability(self) -> bool:
        """
        Verify ledger immutability by checking record count never decreases
        
        Returns:
            bool: True if immutability verified
        """
        try:
            current_count = self.get_trade_count()
            
            # Store count for next verification
            if not hasattr(self, '_last_known_count'):
                self._last_known_count = current_count
                return True
            
            # Check count never decreased
            if current_count < self._last_known_count:
                logger.error(
                    f"IMMUTABILITY VIOLATION: Record count decreased from "
                    f"{self._last_known_count} to {current_count}"
                )
                return False
            
            # Update last known count
            self._last_known_count = current_count
            return True
            
        except Exception as e:
            logger.error(f"Error verifying immutability: {e}")
            return False
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics from ledger
        
        Returns:
            Dict: Summary statistics
        """
        df = self.read_all()
        closed_df = self.read_closed_trades()
        
        if len(closed_df) == 0:
            return {
                'total_entries': len(df),
                'closed_trades': 0,
                'open_trades': len(df[df['action'] == 'open']),
                'total_net_pnl': 0.0,
                'total_tax_paid': 0.0,
                'win_rate': 0.0,
                'avg_days_held': 0.0,
            }
        
        # Calculate statistics
        total_net_pnl = closed_df['net_pnl'].sum()
        total_tax_paid = closed_df['tax'].sum()
        winning_trades = len(closed_df[closed_df['net_pnl'] > 0])
        win_rate = winning_trades / len(closed_df) if len(closed_df) > 0 else 0.0
        avg_days_held = closed_df['days_held'].mean()
        
        return {
            'total_entries': len(df),
            'closed_trades': len(closed_df),
            'open_trades': len(df[df['action'] == 'open']) - len(closed_df),
            'total_net_pnl': total_net_pnl,
            'total_tax_paid': total_tax_paid,
            'win_rate': win_rate,
            'avg_days_held': avg_days_held,
            'winning_trades': winning_trades,
            'losing_trades': len(closed_df) - winning_trades,
        }
