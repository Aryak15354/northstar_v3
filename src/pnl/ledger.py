"""
UnifiedPnLLedger — The immutable master record of all P&L events in Northstar V3.

Design principles:
1. APPEND-ONLY: Records are never modified or deleted
2. DOUBLE-ENTRY: Every economic event has entries that net to zero
3. COMPLETE: Every financial event affecting portfolio value is recorded
4. PIT-SAFE: Every entry has trade_date and settlement_date
5. MULTI-BOOK: Separate books for EQUITY, OPTIONS, CASH, SHADOW
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List
from pathlib import Path
import pandas as pd
import uuid
import threading
import logging
import json

logger = logging.getLogger(__name__)


class LedgerEntryType(str, Enum):
    # Equity book
    EQUITY_BUY = "EQUITY_BUY"
    EQUITY_SELL = "EQUITY_SELL"
    EQUITY_MTM = "EQUITY_MTM"
    EQUITY_DIV = "EQUITY_DIV"
    EQUITY_CA = "EQUITY_CA"
    
    # Options book
    OPTIONS_BUY = "OPTIONS_BUY"
    OPTIONS_SELL = "OPTIONS_SELL"
    OPTIONS_EXPIRY = "OPTIONS_EXPIRY"
    OPTIONS_EXERCISE = "OPTIONS_EXERCISE"
    OPTIONS_MTM = "OPTIONS_MTM"
    
    # Cost entries
    TXN_COST = "TXN_COST"
    SLIPPAGE = "SLIPPAGE"
    
    # Cash entries
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"
    
    # Corrections
    CORRECTION = "CORRECTION"
    
    # Shadow book
    SHADOW_BUY = "SHADOW_BUY"
    SHADOW_SELL = "SHADOW_SELL"
    SHADOW_MTM = "SHADOW_MTM"


class LedgerBook(str, Enum):
    EQUITY = "EQUITY"
    OPTIONS = "OPTIONS"
    CASH = "CASH"
    SHADOW = "SHADOW"


@dataclass
class LedgerEntry:
    """Single immutable ledger entry"""
    entry_id: str
    entry_type: LedgerEntryType
    book: LedgerBook
    
    trade_date: datetime
    settlement_date: datetime
    recorded_at: datetime
    
    ticker: Optional[str]
    quantity: float
    price: float
    notional: float
    
    realized_pnl: float
    unrealized_pnl_change: float
    
    transaction_cost: float
    net_pnl: float
    
    strategy_id: Optional[str]
    signal_strength: Optional[float]
    
    # Options-specific
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[datetime] = None
    greeks_at_entry: Optional[Dict] = None
    
    # Metadata
    source: str = "LIVE"
    notes: Optional[str] = None
    original_entry_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dict for DataFrame storage"""
        d = asdict(self)
        # Convert enums to strings
        d['entry_type'] = self.entry_type.value
        d['book'] = self.book.value
        # Convert datetime to ISO strings
        for field in ['trade_date', 'settlement_date', 'recorded_at', 'expiry']:
            if d[field] is not None:
                d[field] = d[field].isoformat() if isinstance(d[field], datetime) else d[field]
        # Convert dict to JSON string
        if d['greeks_at_entry'] is not None:
            d['greeks_at_entry'] = json.dumps(d['greeks_at_entry'])
        return d


@dataclass
class MigrationResult:
    """Result of legacy data migration"""
    migrated_count: int
    conflict_count: int
    conflicts: List[Dict]
    migration_date: datetime


class UnifiedPnLLedger:
    """
    The single source of truth for all P&L events.
    Append-only, immutable, double-entry accounting ledger.
    """
    
    def __init__(self, ledger_path: str = "data/pnl/master_ledger.parquet", config: dict = None):
        self.ledger_path = Path(ledger_path)
        self.config = config or {}
        self.buffer: List[LedgerEntry] = []
        self.lock = threading.Lock()
        
        # Ensure directory exists
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing ledger
        if self.ledger_path.exists():
            self.ledger_df = pd.read_parquet(self.ledger_path)
            logger.info(f"Loaded existing ledger with {len(self.ledger_df)} entries")
        else:
            self.ledger_df = pd.DataFrame()
            logger.info("Initialized empty ledger")
    
    def record(self, entry: LedgerEntry) -> str:
        """
        Record a new entry to the ledger buffer.
        Thread-safe. Returns entry_id.
        """
        with self.lock:
            # Validate entry
            self._validate_entry(entry)
            
            # Add to buffer
            self.buffer.append(entry)
            
            logger.debug(f"Recorded {entry.entry_type.value} for {entry.ticker}: {entry.net_pnl:.2f}")
            
            return entry.entry_id
    
    def _validate_entry(self, entry: LedgerEntry):
        """Validate entry consistency"""
        # Required fields
        if entry.entry_id is None or entry.entry_id == "":
            raise ValueError("entry_id is required")
        
        if entry.trade_date is None:
            raise ValueError("trade_date is required")
        
        # Sign consistency for equity trades (not options - options can have complex positions)
        if entry.entry_type in [LedgerEntryType.EQUITY_BUY]:
            if entry.quantity <= 0:
                raise ValueError(f"EQUITY_BUY entries must have positive quantity, got {entry.quantity}")
        
        if entry.entry_type in [LedgerEntryType.EQUITY_SELL]:
            if entry.quantity >= 0:
                raise ValueError(f"EQUITY_SELL entries must have negative quantity, got {entry.quantity}")
        
        # Options trades can have any sign depending on strategy (buying puts, selling calls, etc.)
        # So we don't validate sign for options
        
        # Transaction costs should be negative (they reduce P&L)
        if entry.transaction_cost > 0:
            logger.warning(f"Transaction cost is positive: {entry.transaction_cost}. Should be negative.")
    
    def record_equity_trade(
        self,
        ticker: str,
        quantity: float,
        price: float,
        strategy_id: Optional[str],
        transaction_cost: float,
        trade_date: Optional[datetime] = None,
        source: str = 'LIVE'
    ) -> str:
        """Convenience method for equity trades"""
        if trade_date is None:
            trade_date = datetime.now()
        
        # Determine entry type from quantity sign
        if quantity > 0:
            entry_type = LedgerEntryType.SHADOW_BUY if source == 'PAPER' else LedgerEntryType.EQUITY_BUY
        else:
            entry_type = LedgerEntryType.SHADOW_SELL if source == 'PAPER' else LedgerEntryType.EQUITY_SELL
        
        # Settlement date is T+1 for Indian equities
        settlement_date = self._add_business_days(trade_date, 1)
        
        notional = abs(quantity * price)
        
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=entry_type,
            book=LedgerBook.SHADOW if source == 'PAPER' else LedgerBook.EQUITY,
            trade_date=trade_date,
            settlement_date=settlement_date,
            recorded_at=datetime.now(),
            ticker=ticker,
            quantity=quantity,
            price=price,
            notional=notional,
            realized_pnl=0.0,  # Will be computed on close
            unrealized_pnl_change=0.0,
            transaction_cost=transaction_cost,
            net_pnl=transaction_cost,  # Opening trade only has cost
            strategy_id=strategy_id,
            signal_strength=None,
            source=source
        )
        
        return self.record(entry)
    
    def record_options_trade(
        self,
        ticker: str,
        quantity: float,
        price: float,
        option_type: str,
        strike: float,
        expiry: datetime,
        greeks: Dict,
        strategy_id: Optional[str],
        transaction_cost: float,
        trade_date: Optional[datetime] = None,
        source: str = 'LIVE'
    ) -> str:
        """Convenience method for options trades"""
        if trade_date is None:
            trade_date = datetime.now()
        
        # Options premium settles same day in India
        settlement_date = trade_date
        
        # Determine entry type
        if quantity > 0:
            entry_type = LedgerEntryType.OPTIONS_BUY
        else:
            entry_type = LedgerEntryType.OPTIONS_SELL
        
        notional = abs(quantity * price)
        
        entry = LedgerEntry(
            entry_id=str(uuid.uuid4()),
            entry_type=entry_type,
            book=LedgerBook.OPTIONS,
            trade_date=trade_date,
            settlement_date=settlement_date,
            recorded_at=datetime.now(),
            ticker=ticker,
            quantity=quantity,
            price=price,
            notional=notional,
            realized_pnl=0.0,
            unrealized_pnl_change=0.0,
            transaction_cost=transaction_cost,
            net_pnl=transaction_cost,
            strategy_id=strategy_id,
            signal_strength=None,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            greeks_at_entry=greeks,
            source=source
        )
        
        return self.record(entry)
    
    def _prior_cumulative_unrealized(
        self,
        entry_type: "LedgerEntryType",
        original_entry_id: str,
        before_date: datetime,
        lot_key: Optional[str] = None,
    ) -> float:
        """
        Reconstruct the cumulative unrealized P&L already recognized for a
        position as of the most recent prior mark, by summing this position's
        past unrealized_pnl_change entries (each of which is itself a daily
        delta once written by this method). Returns 0.0 if no prior mark
        exists, which naturally gives day-1 semantics (first mark's delta ==
        its own total).

        `lot_key`, when provided (equity), guards against summing across a
        close-then-reopen cycle on the same ticker: entries are scanned
        newest-first and summation stops as soon as a prior entry's recorded
        lot_key (its avg_cost at the time) no longer matches the current one,
        since that means the earlier entries belong to a different, already
        -closed lot. Options positions pass lot_key=None because position_id
        is minted fresh on every open and is never reused, so no such guard
        is needed.
        """
        candidates: List[tuple] = []

        for buffered in self.buffer:
            if (
                buffered.entry_type == entry_type
                and buffered.original_entry_id == original_entry_id
                and buffered.trade_date < before_date
            ):
                candidates.append((buffered.trade_date, buffered.unrealized_pnl_change, buffered.notes))

        if len(self.ledger_df) > 0 and {'entry_type', 'original_entry_id', 'trade_date'}.issubset(self.ledger_df.columns):
            df = self.ledger_df
            trade_dates = pd.to_datetime(df['trade_date'], format='mixed', errors='coerce')
            mask = (
                (df['entry_type'] == entry_type.value)
                & (df['original_entry_id'] == original_entry_id)
                & (trade_dates < before_date)
            )
            matched = df.loc[mask]
            for trade_date, delta, notes in zip(
                trade_dates[mask], matched['unrealized_pnl_change'], matched.get('notes', pd.Series(dtype=object))
            ):
                candidates.append((trade_date, float(delta), notes))

        if not candidates:
            return 0.0

        candidates.sort(key=lambda row: row[0], reverse=True)

        total = 0.0
        for _, delta, notes in candidates:
            if lot_key is not None and notes != lot_key:
                break
            total += delta

        return total

    def record_eod_mark(
        self,
        date: datetime,
        equity_positions: Dict,
        equity_prices: Dict,
        options_positions: Dict,
        options_prices: Dict
    ) -> None:
        """
        Record end-of-day mark-to-market for all open positions.
        Called by eod_rebalance.py every evening.

        Writes the day's INCREMENTAL unrealized P&L change into
        unrealized_pnl_change/net_pnl (not the position's total unrealized
        P&L since entry), because NAVCalculator and get_total_pnl() both sum
        net_pnl across days to reconstruct cumulative P&L. Writing the total
        every day would make NAV double/triple/n-count the same gain for
        every day a position stays open without a new trade.
        """
        logger.info(f"Recording EOD mark for {date.date()}")

        # Mark equity positions
        for ticker, position in equity_positions.items():
            if ticker not in equity_prices:
                logger.warning(f"No EOD price for {ticker}, skipping MTM")
                continue

            current_price = equity_prices[ticker]
            quantity = position.get('quantity', 0)

            if quantity == 0:
                continue

            # Compute total unrealized P&L since entry, then convert to a
            # daily delta by subtracting what was already recognized in
            # prior marks for this same lot (see _prior_cumulative_unrealized).
            avg_cost = position.get('avg_cost', current_price)
            lot_key = f"avg_cost={avg_cost:.6f}"
            total_unrealized_pnl = (current_price - avg_cost) * quantity
            prior_cumulative = self._prior_cumulative_unrealized(
                LedgerEntryType.EQUITY_MTM, ticker, date, lot_key=lot_key
            )
            unrealized_pnl_change = total_unrealized_pnl - prior_cumulative

            entry = LedgerEntry(
                entry_id=str(uuid.uuid4()),
                entry_type=LedgerEntryType.EQUITY_MTM,
                book=LedgerBook.EQUITY,
                trade_date=date,
                settlement_date=date,
                recorded_at=datetime.now(),
                ticker=ticker,
                quantity=quantity,
                price=current_price,
                notional=abs(quantity * current_price),
                realized_pnl=0.0,
                unrealized_pnl_change=unrealized_pnl_change,
                transaction_cost=0.0,
                net_pnl=unrealized_pnl_change,
                strategy_id=position.get('strategy_id'),
                signal_strength=None,
                source='LIVE',
                notes=lot_key,
                original_entry_id=ticker,
            )

            self.record(entry)

        # Mark options positions
        for position_id, position in options_positions.items():
            ticker = position.get('underlying')
            if ticker not in options_prices:
                logger.warning(f"No EOD price for options on {ticker}, skipping MTM")
                continue

            current_value = options_prices.get(position_id, 0)
            entry_value = position.get('entry_credit_debit', 0)

            # position_id is minted fresh per open and never reused (see
            # src/options/position_manager.py), so no lot_key guard is needed
            # here the way it is for equity tickers.
            total_unrealized_pnl = current_value - entry_value
            prior_cumulative = self._prior_cumulative_unrealized(
                LedgerEntryType.OPTIONS_MTM, position_id, date
            )
            unrealized_pnl_change = total_unrealized_pnl - prior_cumulative

            entry = LedgerEntry(
                entry_id=str(uuid.uuid4()),
                entry_type=LedgerEntryType.OPTIONS_MTM,
                book=LedgerBook.OPTIONS,
                trade_date=date,
                settlement_date=date,
                recorded_at=datetime.now(),
                ticker=ticker,
                quantity=position.get('quantity', 0),
                price=current_value,
                notional=abs(current_value),
                realized_pnl=0.0,
                unrealized_pnl_change=unrealized_pnl_change,
                transaction_cost=0.0,
                net_pnl=unrealized_pnl_change,
                strategy_id=position.get('strategy_id'),
                signal_strength=None,
                source='LIVE',
                original_entry_id=position_id,
            )

            self.record(entry)
    
    def flush(self) -> None:
        """Write buffer to disk atomically"""
        with self.lock:
            if not self.buffer:
                logger.debug("No entries to flush")
                return
            
            # Convert buffer to DataFrame
            buffer_dicts = [entry.to_dict() for entry in self.buffer]
            buffer_df = pd.DataFrame(buffer_dicts)
            
            # Append to existing ledger
            if len(self.ledger_df) > 0:
                self.ledger_df = pd.concat([self.ledger_df, buffer_df], ignore_index=True)
            else:
                self.ledger_df = buffer_df
            
            # Write to disk
            self.ledger_df.to_parquet(self.ledger_path, index=False)
            
            logger.info(f"Flushed {len(self.buffer)} entries to {self.ledger_path}")
            
            # Clear buffer
            self.buffer = []
    
    def query(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        books: Optional[List[LedgerBook]] = None,
        entry_types: Optional[List[LedgerEntryType]] = None,
        tickers: Optional[List[str]] = None,
        strategy_ids: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Flexible query interface for ledger entries"""
        df = self.ledger_df.copy()
        
        if len(df) == 0:
            return df
        
        # Ensure trade_date is datetime
        if 'trade_date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['trade_date']):
            df['trade_date'] = pd.to_datetime(df['trade_date'], format='mixed')
        
        # Apply filters
        if start_date is not None:
            df = df[df['trade_date'] >= start_date]
        
        if end_date is not None:
            df = df[df['trade_date'] <= end_date]
        
        if books is not None:
            book_values = [b.value if isinstance(b, LedgerBook) else b for b in books]
            df = df[df['book'].isin(book_values)]
        
        if entry_types is not None:
            type_values = [t.value if isinstance(t, LedgerEntryType) else t for t in entry_types]
            df = df[df['entry_type'].isin(type_values)]
        
        if tickers is not None:
            df = df[df['ticker'].isin(tickers)]
        
        if strategy_ids is not None:
            df = df[df['strategy_id'].isin(strategy_ids)]
        
        return df
    
    def get_realized_pnl(
        self,
        start_date: datetime,
        end_date: datetime,
        book: Optional[LedgerBook] = None
    ) -> float:
        """Get total realized P&L over period"""
        df = self.query(start_date=start_date, end_date=end_date, books=[book] if book else None)
        
        if len(df) == 0:
            return 0.0
        
        # Exclude MTM entries (they're unrealized)
        mtm_types = [LedgerEntryType.EQUITY_MTM.value, LedgerEntryType.OPTIONS_MTM.value, LedgerEntryType.SHADOW_MTM.value]
        df = df[~df['entry_type'].isin(mtm_types)]
        
        return df['realized_pnl'].sum()
    
    def get_total_pnl(
        self,
        as_of_date: datetime,
        book: Optional[LedgerBook] = None
    ) -> float:
        """Get total P&L (realized + unrealized) as of date"""
        df = self.query(end_date=as_of_date, books=[book] if book else None)
        
        if len(df) == 0:
            return 0.0
        
        return df['net_pnl'].sum()
    
    def get_open_positions(
        self,
        as_of_date: datetime,
        book: Optional[LedgerBook] = None
    ) -> pd.DataFrame:
        """Reconstruct open positions as of any date"""
        df = self.query(end_date=as_of_date, books=[book] if book else None)
        
        if len(df) == 0:
            return pd.DataFrame(columns=['ticker', 'book', 'quantity', 'avg_cost', 'unrealized_pnl'])
        
        # Group by ticker and book
        positions = []
        
        for (ticker, book_val), group in df.groupby(['ticker', 'book']):
            if ticker is None:
                continue
            
            # Sum quantities (buys positive, sells negative)
            total_qty = group['quantity'].sum()
            
            if abs(total_qty) < 0.001:  # Position is closed
                continue
            
            # Compute average cost
            cost_basis = (group['quantity'] * group['price']).sum()
            avg_cost = cost_basis / total_qty if total_qty != 0 else 0
            
            # unrealized_pnl_change on each MTM row is a daily delta (see
            # record_eod_mark), so the position's current cumulative
            # unrealized P&L is the sum of all its MTM deltas, not the most
            # recent row alone. Note: like avg_cost above, this sums across
            # the ticker's whole history in `df`, so a ticker that was fully
            # closed and reopened within the query window will overstate
            # both figures by including the earlier, already-closed lot.
            mtm_rows = group[group['entry_type'].str.contains('MTM')]
            unrealized_pnl = mtm_rows['unrealized_pnl_change'].sum() if len(mtm_rows) > 0 else 0
            
            positions.append({
                'ticker': ticker,
                'book': book_val,
                'quantity': total_qty,
                'avg_cost': avg_cost,
                'unrealized_pnl': unrealized_pnl
            })
        
        return pd.DataFrame(positions)
    
    def correct(
        self,
        original_entry_id: str,
        corrected_entry: LedgerEntry,
        reason: str
    ) -> str:
        """Record a correction (original entry is NOT modified)"""
        corrected_entry.entry_type = LedgerEntryType.CORRECTION
        corrected_entry.original_entry_id = original_entry_id
        corrected_entry.notes = f"CORRECTION: {reason}"
        
        return self.record(corrected_entry)
    
    def migrate_legacy_data(self) -> MigrationResult:
        """
        One-time migration from the five legacy P&L locations.
        Returns MigrationResult with conflicts for manual review.
        """
        logger.info("Starting legacy data migration...")
        
        conflicts = []
        migrated_count = 0
        
        # Migration order (most to least trusted)
        migrations = [
            self._migrate_options_ledger,
            self._migrate_portfolio_pnl,
            self._migrate_shadow_pnl,
            self._migrate_simulation_metrics,
            self._migrate_paper_trading_log,
        ]
        
        for migrate_func in migrations:
            try:
                count, func_conflicts = migrate_func()
                migrated_count += count
                conflicts.extend(func_conflicts)
            except Exception as e:
                logger.error(f"Migration error in {migrate_func.__name__}: {e}")
        
        # Write conflicts to file
        if conflicts:
            conflict_path = Path("data/pnl/migration_conflicts.json")
            with open(conflict_path, 'w') as f:
                json.dump(conflicts, f, indent=2, default=str)
            logger.warning(f"Found {len(conflicts)} conflicts, written to {conflict_path}")
        
        # Flush all migrated entries
        self.flush()
        
        result = MigrationResult(
            migrated_count=migrated_count,
            conflict_count=len(conflicts),
            conflicts=conflicts,
            migration_date=datetime.now()
        )
        
        logger.info(f"Migration complete: {migrated_count} entries, {len(conflicts)} conflicts")
        
        return result
    
    def _migrate_options_ledger(self):
        """Migrate from data/options/trade_ledger.parquet"""
        path = Path("data/options/trade_ledger.parquet")
        if not path.exists():
            return 0, []
        
        df = pd.read_parquet(path)
        count = 0
        conflicts = []
        
        for _, row in df.iterrows():
            # Parse legs JSON
            try:
                legs = json.loads(row['legs']) if isinstance(row['legs'], str) else row['legs']
            except:
                legs = []
            
            # Create entry for each leg
            for leg in legs:
                entry = LedgerEntry(
                    entry_id=f"MIGRATED_OPTIONS_{row['trade_id']}_{leg.get('symbol', '')}",
                    entry_type=LedgerEntryType.OPTIONS_BUY if leg.get('action') == 'BUY' else LedgerEntryType.OPTIONS_SELL,
                    book=LedgerBook.OPTIONS,
                    trade_date=pd.to_datetime(row['timestamp']),
                    settlement_date=pd.to_datetime(row['timestamp']),
                    recorded_at=datetime.now(),
                    ticker=row['underlying'],
                    quantity=leg.get('quantity', 0),
                    price=leg.get('entry_premium', 0),
                    notional=abs(leg.get('quantity', 0) * leg.get('entry_premium', 0)),
                    realized_pnl=row.get('gross_pnl', 0) if pd.notna(row.get('gross_pnl')) else 0,
                    unrealized_pnl_change=0,
                    transaction_cost=-(row.get('costs', 0) + row.get('tax', 0)) if pd.notna(row.get('costs')) else 0,
                    net_pnl=row.get('net_pnl', 0) if pd.notna(row.get('net_pnl')) else 0,
                    strategy_id=row.get('strategy_type'),
                    signal_strength=None,
                    option_type=leg.get('option_type'),
                    strike=leg.get('strike'),
                    expiry=pd.to_datetime(row['expiry']),
                    greeks_at_entry={'delta': leg.get('delta'), 'gamma': leg.get('gamma'), 'theta': leg.get('theta'), 'vega': leg.get('vega')},
                    source='MIGRATION',
                    notes=f"Migrated from options trade_ledger, trade_id={row['trade_id']}"
                )
                
                self.record(entry)
                count += 1
        
        logger.info(f"Migrated {count} entries from options ledger")
        return count, conflicts
    
    def _migrate_portfolio_pnl(self):
        """Migrate from data/portfolio/pnl_on_paper.parquet"""
        path = Path("data/portfolio/pnl_on_paper.parquet")
        if not path.exists():
            return 0, []
        
        df = pd.read_parquet(path)
        count = 0
        conflicts = []
        
        # This file has daily equity values, not individual trades
        # We'll create daily MTM entries
        for _, row in df.iterrows():
            date = pd.to_datetime(row['Date'])
            daily_return = row.get('Return', 0)
            equity_value = row.get('Equity', 0)
            
            if daily_return == 0:
                continue
            
            entry = LedgerEntry(
                entry_id=f"MIGRATED_EQUITY_MTM_{date.strftime('%Y%m%d')}",
                entry_type=LedgerEntryType.EQUITY_MTM,
                book=LedgerBook.EQUITY,
                trade_date=date,
                settlement_date=date,
                recorded_at=datetime.now(),
                ticker="PORTFOLIO",
                quantity=0,
                price=equity_value,
                notional=equity_value,
                realized_pnl=0,
                unrealized_pnl_change=daily_return * equity_value,
                transaction_cost=0,
                net_pnl=daily_return * equity_value,
                strategy_id=None,
                signal_strength=None,
                source='MIGRATION',
                notes="Migrated from portfolio pnl_on_paper"
            )
            
            self.record(entry)
            count += 1
        
        logger.info(f"Migrated {count} entries from portfolio P&L")
        return count, conflicts
    
    def _migrate_shadow_pnl(self):
        """Migrate from data/execution/shadow_pnl.parquet"""
        path = Path("data/execution/shadow_pnl.parquet")
        if not path.exists():
            return 0, []
        
        df = pd.read_parquet(path)
        count = 0
        
        for _, row in df.iterrows():
            date = pd.to_datetime(row['timestamp'])
            unrealized_pnl = row.get('unrealized_pnl', 0)
            
            entry = LedgerEntry(
                entry_id=f"MIGRATED_SHADOW_{date.strftime('%Y%m%d_%H%M%S')}",
                entry_type=LedgerEntryType.SHADOW_MTM,
                book=LedgerBook.SHADOW,
                trade_date=date,
                settlement_date=date,
                recorded_at=datetime.now(),
                ticker="SHADOW_PORTFOLIO",
                quantity=0,
                price=row.get('total_portfolio_value', 0),
                notional=row.get('market_value', 0),
                realized_pnl=0,
                unrealized_pnl_change=unrealized_pnl,
                transaction_cost=0,
                net_pnl=unrealized_pnl,
                strategy_id=None,
                signal_strength=None,
                source='MIGRATION',
                notes="Migrated from shadow P&L"
            )
            
            self.record(entry)
            count += 1
        
        logger.info(f"Migrated {count} entries from shadow P&L")
        return count, []
    
    def _migrate_simulation_metrics(self):
        """Migrate from data/simulation/daily_portfolio_metrics.parquet"""
        # This is simulation data, not live P&L - skip for now
        return 0, []
    
    def _migrate_paper_trading_log(self):
        """Migrate from data/paper_trading/performance_log.csv"""
        path = Path("data/paper_trading/performance_log.csv")
        if not path.exists():
            return 0, []
        
        df = pd.read_csv(path)
        count = 0
        
        for _, row in df.iterrows():
            date = pd.to_datetime(row['week_end'])
            portfolio_return = row.get('portfolio_return', 0)
            
            if portfolio_return == 0:
                continue
            
            entry = LedgerEntry(
                entry_id=f"MIGRATED_PAPER_{date.strftime('%Y%m%d')}",
                entry_type=LedgerEntryType.EQUITY_MTM,
                book=LedgerBook.EQUITY,
                trade_date=date,
                settlement_date=date,
                recorded_at=datetime.now(),
                ticker="PAPER_PORTFOLIO",
                quantity=0,
                price=0,
                notional=0,
                realized_pnl=0,
                unrealized_pnl_change=portfolio_return,
                transaction_cost=0,
                net_pnl=portfolio_return,
                strategy_id=None,
                signal_strength=None,
                source='MIGRATION',
                notes=f"Migrated from paper trading log, regime={row.get('regime')}"
            )
            
            self.record(entry)
            count += 1
        
        logger.info(f"Migrated {count} entries from paper trading log")
        return count, []
    
    def _add_business_days(self, date: datetime, days: int) -> datetime:
        """Add business days to a date (simple version, doesn't account for holidays)"""
        current = date
        while days > 0:
            current += timedelta(days=1)
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                days -= 1
        return current
