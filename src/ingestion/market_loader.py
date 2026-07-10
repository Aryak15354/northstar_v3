"""
MarketLoader — Load daily price data for all 504 Nifty 500 tickers plus index data.

Data sources:
- data/raw/prices_daily/ — Individual CSV files per ticker
- data/canonical/prices/equity_prices_daily.parquet — Canonical pre-merged version
- data/universe/ — Universe snapshots, corporate actions, delistings, symbol migrations

Handles:
- Corporate actions (splits, dividends)
- Delistings
- Symbol migrations
- Survivorship bias prevention
- Forward returns (with mode='research' vs mode='live' distinction)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

from src.data.price_access import canonical_price_path

from .base_loader import BaseLoader, DataNotFoundError, PITViolationError

logger = logging.getLogger(__name__)


class MarketLoader(BaseLoader):
    """Loads daily price data with corporate action adjustments and PIT enforcement."""

    _FIELD_ALIASES = {
        'open': ['Open', 'open'],
        'high': ['High', 'high'],
        'low': ['Low', 'low'],
        'close': ['Close', 'close', 'Adj Close', 'adj_close'],
        'adj_close': ['Adj Close', 'adj_close', 'Close', 'close'],
        'volume': ['Volume', 'volume'],
    }

    _INDEX_FILE_ALIASES = {
        'NIFTY500': 'nifty_500.parquet',
        'NIFTY 500': 'nifty_500.parquet',
        'NIFTY_500': 'nifty_500.parquet',
    }
    
    def load(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        start_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Load daily price data as of a specific date.
        
        Args:
            as_of_date: Point-in-time date for data loading
            tickers: List of tickers to load (None = all universe tickers)
            fields: List of price fields to return (None = all OHLCV + Adjusted Close)
            start_date: How far back to load (None = use config default)
            
        Returns:
            MultiIndex DataFrame with (Date, Ticker) as index and price fields as columns
        """
        start_time = pd.Timestamp.now()
        
        # Generate cache key
        ticker_key = ','.join(sorted(tickers)) if tickers else 'all'
        field_key = ','.join(sorted(fields)) if fields else 'all'
        start_key = start_date.isoformat() if start_date else 'default'
        cache_key = f"market_{as_of_date.date()}_{ticker_key}_{field_key}_{start_key}"
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Determine tickers to load
        if tickers is None:
            tickers = self.get_universe_as_of(as_of_date)
        
        # Normalize tickers - add .NS suffix if not present (Yahoo Finance format)
        normalized_tickers = []
        for ticker in tickers:
            if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                normalized_tickers.append(f"{ticker}.NS")
            else:
                normalized_tickers.append(ticker)
        
        # Determine start date
        if start_date is None:
            lookback_days = self.config.get('market_data_lookback_days', 1095)  # 3 years default
            start_date = as_of_date - timedelta(days=lookback_days)
        
        # Active runtime reads canonical prices only; builders own legacy ingestion.
        prices_path = canonical_price_path(project_root=Path.cwd())
        
        if prices_path.exists() and prices_path.suffix == '.parquet':
            df = self._load_from_parquet(prices_path, normalized_tickers, start_date, as_of_date)
        else:
            # Fall back to loading individual CSV files
            raw_dir = self._resolve_path('prices_daily', 'data/raw/prices_daily')
            df = self._load_from_csv_files(raw_dir, normalized_tickers, start_date, as_of_date)
        
        if df.empty:
            logger.warning(f"No price data loaded for {len(tickers)} tickers")
            return df
        
        # Apply corporate actions
        df = self._apply_corporate_actions(df, as_of_date)
        
        # Handle delistings
        df = self._handle_delistings(df, as_of_date)
        
        # Handle symbol migrations
        df = self._handle_symbol_migrations(df, as_of_date)

        # Standardize common market column names before field selection.
        df = self._standardize_market_columns(df)

        # Filter fields if specified
        if fields:
            df = self._select_requested_fields(df, fields)
            if df.empty:
                logger.warning(f"None of the requested fields {fields} found in data")

        # PIT enforcement
        if 'Date' in df.index.names:
            # Reset index temporarily for validation
            df_temp = df.reset_index()
            self._validate_pit(df_temp, 'Date', as_of_date)
            df = df_temp.set_index(['Date', 'Ticker'])
        
        # Check freshness
        if not df.empty:
            latest_date = df.index.get_level_values('Date').max()
            age_days = (as_of_date.date() - latest_date.date()).days if hasattr(latest_date, 'date') else 0
            
            soft_threshold = self.staleness_config.get('market_data_soft_hours', 48) / 24
            hard_threshold = self.staleness_config.get('market_data_hard_hours', 120) / 24
            
            if age_days > hard_threshold:
                from .base_loader import StaleDataError
                raise StaleDataError(
                    f"Market data critically stale: latest date is {latest_date}, "
                    f"{age_days} days before {as_of_date.date()}"
                )
            elif age_days > soft_threshold:
                logger.warning(
                    f"Market data stale: latest date is {latest_date}, "
                    f"{age_days} days before {as_of_date.date()}"
                )
        
        # Log and cache
        elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000
        self._log_load(len(df), len(df.columns), str(prices_path), elapsed_ms, as_of_date)
        self._set_cached(cache_key, df)
        
        return df

    def _standardize_market_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize common market column names without breaking existing callers."""
        if df.empty:
            return df
        out = df.copy()
        rename_map = {}
        if 'ticker' in out.columns and 'Ticker' not in out.columns:
            rename_map['ticker'] = 'Ticker'
        if 'date' in out.columns and 'Date' not in out.columns:
            rename_map['date'] = 'Date'
        if rename_map:
            out = out.rename(columns=rename_map)

        if isinstance(out.index, pd.MultiIndex):
            names = list(out.index.names)
            if len(names) >= 2:
                names = ['Date' if str(n).lower() == 'date' else 'Ticker' if str(n).lower() == 'ticker' else n for n in names]
                out.index = out.index.set_names(names)
        elif out.index.name and str(out.index.name).lower() == 'date':
            out.index = out.index.set_names(['Date'])
        return out

    def _select_requested_fields(self, df: pd.DataFrame, fields: List[str]) -> pd.DataFrame:
        """
        Return a DataFrame whose columns match the requested canonical field names.

        The loader accepts lower-case factor-facing aliases while preserving the
        legacy native-column behavior when no explicit field list is requested.
        """
        if df.empty:
            return df

        selected: dict[str, pd.Series] = {}
        for field in list(fields or []):
            field_name = str(field)
            candidates = []
            if field_name in df.columns:
                candidates.append(field_name)
            candidates.extend(self._FIELD_ALIASES.get(field_name.lower(), []))
            chosen = next((c for c in candidates if c in df.columns), None)
            if chosen is None:
                continue
            selected[field_name] = df[chosen]

        if not selected:
            return pd.DataFrame(index=df.index)

        return pd.DataFrame(selected, index=df.index)
    
    def _load_from_parquet(
        self,
        path: Path,
        tickers: List[str],
        start_date: datetime,
        as_of_date: datetime
    ) -> pd.DataFrame:
        """Load from pre-merged parquet file."""
        try:
            df = pd.read_parquet(path)
            
            # Standardize column names (handle both 'ticker' and 'Ticker')
            if 'ticker' in df.columns:
                df = df.rename(columns={'ticker': 'Ticker'})
            
            # Ensure Date column exists
            if 'Date' not in df.columns and 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            
            # Convert Date to datetime if not already
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
            
                # Filter by date range
                df = df[(df['Date'] >= start_date) & (df['Date'] <= as_of_date)]
            
            # Filter by tickers
            if 'Ticker' in df.columns:
                df = df[df['Ticker'].isin(tickers)]
            
            # Set MultiIndex if both columns exist
            if 'Date' in df.columns and 'Ticker' in df.columns:
                df = df.set_index(['Date', 'Ticker'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading from parquet: {e}")
            return pd.DataFrame()
    
    def _load_from_csv_files(
        self,
        raw_dir: Path,
        tickers: List[str],
        start_date: datetime,
        as_of_date: datetime
    ) -> pd.DataFrame:
        """Load from individual CSV files (fallback method)."""
        if not raw_dir.exists():
            raise DataNotFoundError(f"Raw price directory not found: {raw_dir}")
        
        dfs = []
        
        for ticker in tickers:
            # Try different file naming conventions
            possible_files = [
                raw_dir / f"{ticker}.csv",
                raw_dir / f"{ticker.replace('.NS', '')}.NS.csv",  # Without suffix
                raw_dir / f"{ticker}.BO.csv",  # Yahoo Finance format
                raw_dir / "Data" / f"{ticker}.csv",  # Nested directory
                raw_dir / "Data" / f"{ticker}.BO.csv",  # Nested directory
            ]
            
            file_path = None
            for p in possible_files:
                if p.exists():
                    file_path = p
                    break
            
            if not file_path:
                logger.debug(f"No price file found for {ticker}")
                continue
            
            try:
                ticker_df = pd.read_csv(file_path)
                
                # Standardize column names
                ticker_df.columns = [c.strip().title() for c in ticker_df.columns]
                
                # Ensure Date column
                if 'Date' not in ticker_df.columns:
                    logger.warning(f"No Date column in {file_path}")
                    continue
                
                ticker_df['Date'] = pd.to_datetime(ticker_df['Date'])
                ticker_df['Ticker'] = ticker
                
                # Filter by date range
                ticker_df = ticker_df[
                    (ticker_df['Date'] >= start_date) &
                    (ticker_df['Date'] <= as_of_date)
                ]
                
                if not ticker_df.empty:
                    dfs.append(ticker_df)
                    
            except Exception as e:
                logger.warning(f"Error loading {file_path}: {e}")
                continue
        
        if not dfs:
            return pd.DataFrame()
        
        df = pd.concat(dfs, ignore_index=True)
        df = df.set_index(['Date', 'Ticker'])
        
        return df
    
    def _apply_corporate_actions(
        self,
        df: pd.DataFrame,
        as_of_date: datetime
    ) -> pd.DataFrame:
        """Corporate-action (split/bonus) adjustment — intentional NO-OP.

        Northstar's price panels are sourced from yfinance with auto_adjust=True
        (see src/ingestion/price_fetcher.py), i.e. they are ALREADY split- and
        dividend-adjusted at the source. Re-applying a split adjustment here would
        DOUBLE-adjust every price before the split date.

        The previous implementation looked for columns (Date/ActionType/Ticker/
        SplitRatio) that do not exist in data/universe/corporate_actions.parquet
        (its schema is symbol/action_date/action_type/action_value), so it always
        early-returned via a debug log — a silent no-op that LOOKED like it might
        be adjusting. This is now an EXPLICIT no-op so nobody "fixes the schema"
        and reintroduces double-adjustment. If a genuinely unadjusted price source
        is ever added, adjustment must be made source-aware here.
        """
        return df
    
    def _handle_delistings(
        self,
        df: pd.DataFrame,
        as_of_date: datetime
    ) -> pd.DataFrame:
        """Trim any price rows AFTER each ticker's delisting date.

        Two fixes vs the previous version:
        1. SCHEMA: data/universe/delisting_database.parquet uses columns
           `symbol`/`delisting_date` (not `Ticker`/`DelistDate`), so the old code
           always early-returned — a silent no-op.
        2. SURVIVORSHIP: the old code removed a delisted ticker's ENTIRE history,
           so a point-in-time panel as-of T lost every stock that later delisted —
           classic survivorship bias, and it contradicted the delisted-price
           backfill the canonical builder deliberately produces. We now KEEP each
           delisted name's real pre-delisting history and only drop rows dated
           after its delisting (data hygiene; real feeds have none, but stale/
           fabricated post-delist rows get removed).
        """
        try:
            delist_path = self._resolve_path('delisting_database', 'data/universe/delisting_database.parquet')
            if not delist_path.exists():
                logger.debug("No delisting database found")
                return df
            if not isinstance(df.index, pd.MultiIndex) or 'Ticker' not in df.index.names:
                return df

            delist_df = pd.read_parquet(delist_path)
            sym_col = next((c for c in ('symbol', 'Ticker', 'ticker') if c in delist_df.columns), None)
            date_col = next((c for c in ('delisting_date', 'DelistDate', 'delist_date') if c in delist_df.columns), None)
            if sym_col is None or date_col is None:
                logger.debug("delisting database missing symbol/date columns")
                return df

            def _norm(sym: object) -> str:
                s = str(sym).strip().upper()
                if not s:
                    return ''
                return s if s.endswith(('.NS', '.BO')) else f"{s}.NS"

            delist_map: dict[str, pd.Timestamp] = {}
            for _, row in delist_df.iterrows():
                t = _norm(row.get(sym_col))
                d = pd.to_datetime(row.get(date_col), errors='coerce')
                if t and pd.notna(d):
                    # keep the earliest delist date if duplicated
                    delist_map[t] = min(delist_map.get(t, d), d)
            if not delist_map:
                return df

            tickers_level = df.index.get_level_values('Ticker')
            dates_level = df.index.get_level_values('Date')
            mapped = pd.to_datetime(pd.Series(tickers_level).map(delist_map).to_numpy())
            keep = mapped.isna() | (dates_level <= mapped)
            trimmed = df[keep.to_numpy()]
            logger.debug("Trimmed %d post-delisting rows across %d names",
                         int(len(df) - len(trimmed)), len(delist_map))
            return trimmed
        except Exception as e:
            logger.debug(f"Error handling delistings: {e}")
        return df
    
    def _handle_symbol_migrations(
        self,
        df: pd.DataFrame,
        as_of_date: datetime
    ) -> pd.DataFrame:
        """Map old symbols to new symbols based on migration history."""
        try:
            migration_path = self._resolve_path('symbol_migrations', 'data/universe/symbol_migration_map.parquet')
            
            if not migration_path.exists():
                logger.debug("No symbol migration map found")
                return df
            
            migration_df = pd.read_parquet(migration_path)

            # SCHEMA FIX: data/universe/symbol_migration_map.parquet uses
            # `original_symbol`/`mapped_ticker` (not OldSymbol/NewSymbol/
            # MigrationDate), so the old code always early-returned — a silent
            # no-op. The map has no date column; a symbol migration is an identity
            # rename (the old ticker IS the new entity), so applying the mapping
            # is point-in-time safe.
            old_col = next((c for c in ('original_symbol', 'OldSymbol', 'old_symbol') if c in migration_df.columns), None)
            new_col = next((c for c in ('mapped_ticker', 'NewSymbol', 'new_symbol') if c in migration_df.columns), None)
            if old_col is None or new_col is None:
                logger.debug("migration map missing old/new symbol columns")
                return df

            def _norm(sym: object) -> str:
                s = str(sym).strip().upper()
                if not s or s in ('NAN', 'NONE'):
                    return ''
                return s if s.endswith(('.NS', '.BO')) else f"{s}.NS"

            symbol_map = {}
            for _, row in migration_df.iterrows():
                o, n = _norm(row.get(old_col)), _norm(row.get(new_col))
                if o and n and o != n:
                    symbol_map[o] = n

            if symbol_map and isinstance(df.index, pd.MultiIndex) and 'Ticker' in df.index.names:
                df = df.reset_index()
                df['Ticker'] = df['Ticker'].replace(symbol_map)
                df = df.set_index(['Date', 'Ticker'])
                logger.debug(f"Applied {len(symbol_map)} symbol migrations")

        except Exception as e:
            logger.debug(f"Error handling symbol migrations: {e}")

        return df
    
    def load_index(
        self,
        as_of_date: datetime,
        indices: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        index_name: Optional[str] = None,
        index: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Load index data (Nifty 500, Nifty 50, sector indices).
        
        Args:
            as_of_date: Point-in-time date
            indices: List of index names (None = all available)
            start_date: How far back to load
            
        Returns:
            DataFrame with (Date, Index) as MultiIndex and OHLCV as columns
        """
        requested = index_name or index
        if requested is None and indices:
            requested = indices[0]
        if requested is None:
            requested = 'NIFTY500'

        normalized = str(requested).strip().upper().replace('-', ' ').replace('_', ' ')
        file_name = self._INDEX_FILE_ALIASES.get(normalized.replace('  ', ' '), None)
        if file_name is None:
            compact = normalized.replace(' ', '')
            file_name = self._INDEX_FILE_ALIASES.get(compact, None)
        if file_name is None:
            logger.warning("Unsupported index requested: %s", requested)
            return pd.DataFrame()

        base_dir = self._resolve_path('index_data', 'data/processed/index_data')
        index_path = base_dir / file_name
        if not index_path.exists():
            logger.warning("Index data file not found: %s", index_path)
            return pd.DataFrame()

        try:
            df = pd.read_parquet(index_path)
        except Exception as exc:
            logger.error("Error loading index data from %s: %s", index_path, exc)
            return pd.DataFrame()

        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
        if 'Date' not in df.columns and 'date' in df.columns:
            df = df.rename(columns={'date': 'Date'})
        if 'Date' not in df.columns and 'index' in df.columns:
            df = df.rename(columns={'index': 'Date'})
        if 'Date' not in df.columns:
            logger.warning("No Date column found in index data: %s", index_path)
            return pd.DataFrame()

        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        if start_date is not None:
            df = df[df['Date'] >= pd.Timestamp(start_date)]
        df = df[df['Date'] <= pd.Timestamp(as_of_date)]
        if df.empty:
            return pd.DataFrame()

        native_cols = {str(c).lower(): c for c in df.columns}
        rename_map = {}
        for lower_name, native_name in native_cols.items():
            if lower_name in {'open', 'high', 'low', 'close', 'adj_close', 'volume'}:
                rename_map[native_name] = lower_name
        df = df.rename(columns=rename_map)

        keep_cols = ['Date'] + [c for c in ['open', 'high', 'low', 'close', 'adj_close', 'volume'] if c in df.columns]
        df = df[keep_cols].set_index('Date').sort_index()

        if fields:
            return self._select_requested_fields(df, fields)
        return df
    
    def load_returns(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        horizon_days: int = 1,
        mode: str = 'research'
    ) -> pd.DataFrame:
        """
        Load forward returns with proper PIT handling.
        
        CRITICAL: In mode='live', forward returns are NaN (unknown future).
        In mode='research', forward returns are computed for backtesting.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            horizon_days: Forward return horizon
            mode: 'research' or 'live'
            
        Returns:
            DataFrame with returns
        """
        # Load prices
        df = self.load(as_of_date, tickers=tickers)
        
        if df.empty or 'Close' not in df.columns:
            return pd.DataFrame()
        
        # Compute forward returns
        df = df.reset_index()
        df = df.sort_values(['Ticker', 'Date'])
        
        df[f'ret_{horizon_days}d'] = df.groupby('Ticker')['Close'].pct_change(horizon_days).shift(-horizon_days)
        
        # In live mode, mask future returns
        if mode == 'live':
            # Find the most recent horizon_days rows per ticker
            df['days_from_end'] = df.groupby('Ticker').cumcount(ascending=False)
            df.loc[df['days_from_end'] < horizon_days, f'ret_{horizon_days}d'] = np.nan
            df = df.drop(columns=['days_from_end'])
        
        df = df.set_index(['Date', 'Ticker'])
        
        return df
    
    def get_universe_as_of(self, as_of_date: datetime) -> List[str]:
        """
        Get the list of tickers in the Nifty 500 universe as of a specific date.
        
        This prevents survivorship bias by using point-in-time universe membership.
        
        Args:
            as_of_date: Date to get universe for
            
        Returns:
            List of ticker symbols
        """
        try:
            history_path = self._resolve_path('nse_universe_history', 'data/reference/nse_universe_history.parquet')
            universe_path = history_path if history_path.exists() else self._resolve_path(
                'universe_snapshots',
                'data/universe/universe_snapshots.parquet',
            )
            
            if not universe_path.exists():
                logger.debug("Universe snapshots not found, using fallback")
                return self._get_fallback_universe()
            
            df = pd.read_parquet(universe_path)

            # New authoritative row-per-ticker PIT format.
            if {'date', 'ticker'}.issubset(set(df.columns)):
                df['date'] = pd.to_datetime(df['date'], errors='coerce')
                df = df.dropna(subset=['date', 'ticker'])
                valid_snapshots = df[df['date'] <= pd.Timestamp(as_of_date)]
                if valid_snapshots.empty:
                    logger.warning("No universe history snapshot found before %s", as_of_date)
                    return self._get_fallback_universe()
                latest_date = valid_snapshots['date'].max()
                latest = valid_snapshots[valid_snapshots['date'] == latest_date].copy()
                if 'available' in latest.columns:
                    latest = latest[latest['available'].fillna(True)]
                if 'tradeable' in latest.columns:
                    latest = latest[latest['tradeable'].fillna(True)]
                tickers = latest['ticker'].astype(str).str.strip().tolist()
                return sorted({t for t in tickers if t})

            # Legacy one-row-per-date snapshot format.
            if 'Date' not in df.columns and df.index.name == 'Date':
                df = df.reset_index()
            if 'Date' not in df.columns:
                logger.debug("No supported Date column in universe snapshots")
                return self._get_fallback_universe()

            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            valid_snapshots = df[df['Date'] <= pd.Timestamp(as_of_date)]
            if valid_snapshots.empty:
                logger.warning("No universe snapshot found before %s", as_of_date)
                return self._get_fallback_universe()

            latest_snapshot = valid_snapshots.loc[valid_snapshots['Date'].idxmax()]
            tickers = latest_snapshot.get('Tickers', [])
            if isinstance(tickers, str):
                tickers = tickers.split(',')
            return [t.strip() for t in tickers if t.strip()]
            
        except Exception as e:
            logger.debug(f"Error loading universe: {e}")
            return self._get_fallback_universe()
    
    def _get_fallback_universe(self) -> List[str]:
        """Fallback universe if snapshots not available."""
        # Try to read from nifty500.csv
        try:
            universe_file = Path('universe/nifty500.csv')
            if universe_file.exists():
                df = pd.read_csv(universe_file)
                ticker_col = next((c for c in df.columns if 'symbol' in c.lower() or 'ticker' in c.lower()), None)
                if ticker_col:
                    return df[ticker_col].dropna().unique().tolist()
        except Exception as e:
            logger.warning(f"Error loading fallback universe: {e}")
        
        # Last resort: return empty list
        logger.error("No universe data available")
        return []
