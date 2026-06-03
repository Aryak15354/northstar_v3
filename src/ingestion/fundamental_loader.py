"""
FundamentalLoader — Load Screener.in fundamental data with correct PIT enforcement.

This is the most PIT-critical loader in the system. Fundamental data has a publication lag:
- Quarterly results: 45-60 days after quarter end
- Annual results: up to 90 days after fiscal year end
- Shareholding patterns: ~21 days after quarter end

The loader enforces these lags to prevent lookahead bias.

Data sources:
- data/raw/vendors/screener/financials/ — Raw financial statements
- data/processed/screener_fundamentals_annual.csv — Processed annual data
- data/processed/screener_shareholding.csv — Shareholding patterns
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .base_loader import BaseLoader, DataNotFoundError

logger = logging.getLogger(__name__)


class FundamentalLoader(BaseLoader):
    """Loads fundamental data with proper reporting lag enforcement."""

    _ANNUAL_FACTOR_PATHS = (
        'data/canonical/fundamentals/fundamentals_annual_panel.csv',
        'data/processed/screener_fundamentals_annual.csv',
    )
    _QUARTERLY_FACTOR_PATHS = (
        'data/canonical/fundamentals/fundamentals_quarterly_panel.csv',
        'data/processed/screener_fundamentals_quarterly.csv',
    )
    _SHAREHOLDING_PATHS = (
        'data/canonical/fundamentals/shareholding_quarterly.csv',
        'data/processed/screener_shareholding.csv',
    )
    
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        """
        Load fundamental data (delegates to load_financials).
        
        Args:
            as_of_date: Point-in-time date
            **kwargs: Additional parameters for load_financials
            
        Returns:
            DataFrame with fundamental data
        """
        return self.load_financials(as_of_date, **kwargs)
    
    def load_financials(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        statement_type: str = 'all',
        frequency: str = 'annual',
        periods: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Load financial statements with PIT enforcement including reporting lags.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            statement_type: 'balance_sheet', 'income_statement', 'cash_flow', or 'all'
            frequency: 'annual' or 'quarterly'
            
        Returns:
            DataFrame with (Ticker, ReportDate, AvailabilityDate) as index
        """
        start_time = pd.Timestamp.now()
        
        # Generate cache key
        ticker_key = ','.join(sorted(tickers)) if tickers else 'all'
        cache_key = f"fundamentals_{as_of_date.date()}_{ticker_key}_{statement_type}_{frequency}"
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached
        
        # Normalize tickers - add .NS suffix if not present
        if tickers:
            normalized_tickers = []
            for ticker in tickers:
                if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                    normalized_tickers.append(f"{ticker}.NS")
                else:
                    normalized_tickers.append(ticker)
            tickers = normalized_tickers
        
        # Determine reporting lag
        if frequency == 'quarterly':
            lag_days = self.reporting_lags.get('quarterly_results', 60)
        else:
            lag_days = self.reporting_lags.get('annual_results', 90)
        
        # Load data based on frequency
        if frequency == 'annual':
            df = self._load_annual_financials(tickers, statement_type)
        else:
            df = self._load_quarterly_financials(tickers, statement_type)
        
        if df.empty:
            logger.warning(f"No fundamental data loaded for {frequency} {statement_type}")
            return df
        
        # Ensure ReportDate column exists
        if 'ReportDate' not in df.columns:
            # Try to find date column
            date_cols = [c for c in df.columns if 'date' in c.lower() or 'period' in c.lower() or 'fiscal' in c.lower()]
            if date_cols:
                df = df.rename(columns={date_cols[0]: 'ReportDate'})
            else:
                logger.error("No date column found in fundamental data")
                return pd.DataFrame()
        
        # Convert to datetime
        df['ReportDate'] = pd.to_datetime(df['ReportDate'], errors='coerce')
        
        # Calculate availability date if not present (report date + lag)
        if 'AvailabilityDate' not in df.columns:
            df['AvailabilityDate'] = df['ReportDate'] + timedelta(days=lag_days)
        else:
            df['AvailabilityDate'] = pd.to_datetime(df['AvailabilityDate'], errors='coerce')
        
        # PIT enforcement: only include data available by as_of_date
        df = df[df['AvailabilityDate'] <= as_of_date].copy()
        
        # Validate PIT
        self._validate_pit(df, 'AvailabilityDate', as_of_date)
        
        # Standardize column names
        df = self._standardize_columns(df)
        
        # Set index
        if 'Ticker' in df.columns:
            index_cols = ['Ticker', 'ReportDate', 'AvailabilityDate']
            df = df.set_index(index_cols)
        
        # Log and cache
        elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000
        self._log_load(len(df), len(df.columns), f"fundamentals_{frequency}", elapsed_ms, as_of_date)
        self._set_cached(cache_key, df)
        
        return df

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(('.NS', '.BO')):
            return s
        if '.' in s:
            s = s.split('.', 1)[0]
        return f"{s}.NS"

    @staticmethod
    def _pick_first(record: dict, *names: str):
        for name in names:
            if name in record and pd.notna(record[name]):
                return record[name]
        lowered = {str(k).lower(): v for k, v in record.items()}
        for name in names:
            key = str(name).lower()
            if key in lowered and pd.notna(lowered[key]):
                return lowered[key]
        return None

    def _read_first_existing_csv(self, paths: tuple[str, ...]) -> pd.DataFrame:
        for raw_path in paths:
            path = Path(raw_path)
            if path.exists():
                return pd.read_csv(path)
        return pd.DataFrame()

    def _load_factor_panel(self, frequency: str = 'annual') -> pd.DataFrame:
        cache_key = f"factor_panel::{frequency}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if frequency == 'annual':
            df = self._read_first_existing_csv(self._ANNUAL_FACTOR_PATHS)
        elif frequency == 'quarterly':
            df = self._read_first_existing_csv(self._QUARTERLY_FACTOR_PATHS)
        elif frequency == 'shareholding':
            df = self._read_first_existing_csv(self._SHAREHOLDING_PATHS)
        else:
            df = pd.DataFrame()

        if df.empty:
            return df

        rename_map = {}
        if 'Ticker' in df.columns and 'ticker' not in df.columns:
            rename_map['Ticker'] = 'ticker'
        if 'ReportDate' in df.columns and 'report_date' not in df.columns:
            rename_map['ReportDate'] = 'report_date'
        if 'AvailabilityDate' in df.columns and 'availability_date' not in df.columns:
            rename_map['AvailabilityDate'] = 'availability_date'
        if 'QuarterEnd' in df.columns and 'quarter_end' not in df.columns:
            rename_map['QuarterEnd'] = 'quarter_end'
        if rename_map:
            df = df.rename(columns=rename_map)

        if 'ticker' in df.columns:
            df['ticker'] = df['ticker'].map(self._normalize_ticker)
        for col in ['report_date', 'availability_date', 'quarter_end']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        self._set_cached(cache_key, df)
        return df

    def get_factor_financials(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        frequency: str = 'annual',
        periods: int = 2,
        reporting_lag_days: Optional[int] = None,
    ) -> Dict[str, dict]:
        """
        Return PIT-safe current/prior financial records for factor construction.

        This adapter hides the mismatch between the repo's raw loader shape and
        the factor library's preferred current/prior contract.
        """
        panel = self._load_factor_panel(frequency=frequency)
        if panel.empty or 'ticker' not in panel.columns:
            return {}

        work = panel.copy()
        normalized_tickers = None
        if tickers:
            normalized_tickers = [self._normalize_ticker(t) for t in tickers]
            work = work[work['ticker'].isin(normalized_tickers)]

        lag_days = (
            int(reporting_lag_days)
            if reporting_lag_days is not None
            else int(self.reporting_lags.get('annual_results', 90) if frequency == 'annual' else self.reporting_lags.get('quarterly_results', 60))
        )
        date_col = 'report_date' if 'report_date' in work.columns else 'quarter_end'
        actual_availability = (
            pd.to_datetime(work['availability_date'], errors='coerce')
            if 'availability_date' in work.columns
            else pd.Series(pd.NaT, index=work.index)
        )
        lagged_availability = (
            pd.to_datetime(work[date_col], errors='coerce') + timedelta(days=int(lag_days))
            if date_col in work.columns
            else pd.Series(pd.NaT, index=work.index)
        )
        if 'availability_date' in work.columns and reporting_lag_days is None:
            effective_availability = actual_availability
        else:
            effective_availability = pd.concat([actual_availability, lagged_availability], axis=1).max(axis=1)
        work = work.copy()
        work['availability_date'] = effective_availability
        work = work[work['availability_date'] <= pd.Timestamp(as_of_date)]

        if work.empty:
            return {}

        if frequency == 'annual':
            fiscal_year_col = next((col for col in ('fiscal_year', 'fiscalYear', 'year') if col in work.columns), None)
            if fiscal_year_col is not None:
                annual_sort_cols = ['ticker', fiscal_year_col]
                for extra in ('report_date', 'availability_date'):
                    if extra in work.columns:
                        annual_sort_cols.append(extra)
                work = work.sort_values(annual_sort_cols, kind='mergesort')
                # Annual factor consumers expect one PIT-safe observation per fiscal year.
                # The canonical annual panel can contain multiple intra-year rows for the
                # same fiscal year; keep the earliest reported record for that year.
                work = work.groupby(['ticker', fiscal_year_col], sort=False, group_keys=False).head(1).copy()

        sort_cols = ['availability_date']
        for extra in ['report_date', 'quarter_end', 'fiscal_year']:
            if extra in work.columns:
                sort_cols.append(extra)

        work = work.sort_values(['ticker'] + sort_cols, kind='mergesort')
        results: Dict[str, dict] = {}
        for ticker, grp in work.groupby('ticker', sort=False):
            grp = grp.tail(int(max(1, periods)))
            rows = list(grp.to_dict(orient='records'))
            if not rows:
                continue
            payload = {'current': self._canonicalize_factor_record(rows[-1])}
            if len(rows) >= 2:
                payload['prior'] = self._canonicalize_factor_record(rows[-2])
            results[str(ticker)] = payload

        if normalized_tickers is not None:
            for ticker in normalized_tickers:
                results.setdefault(ticker, {})
        return results

    def _canonicalize_factor_record(self, record: dict) -> dict:
        get = lambda *names: self._pick_first(record, *names)
        revenue = get('revenue', 'sales', 'screener_revenue', 'screener_sales')
        cost_of_goods = get('cost_of_revenue', 'native_cost_of_revenue')
        total_expenses = get('expenses', 'screener_expenses')

        return {
            'ticker': self._normalize_ticker(get('ticker') or ""),
            'report_date': pd.to_datetime(get('report_date', 'screener_report_date'), errors='coerce'),
            'availability_date': pd.to_datetime(get('availability_date', 'native_availability_date', 'screener_availability_date'), errors='coerce'),
            'net_profit': get('net_profit', 'net_income', 'native_net_income', 'screener_net_profit'),
            'total_assets': get('total_assets', 'native_total_assets', 'screener_total_assets'),
            'cash_from_operations': get(
                'cash_from_operations',
                'operating_cash_flow',
                'cash_from_operating_activity',
                'screener_cash_from_operating_activity',
                'native_operating_cash_flow',
            ),
            'total_borrowings': get('total_borrowings', 'borrowings', 'borrowing', 'total_debt', 'native_total_debt', 'screener_borrowings'),
            'current_assets': get('current_assets'),
            'current_liabilities': get('current_liabilities'),
            'shares_outstanding': get('shares_outstanding', 'native_shares_outstanding'),
            'revenue': revenue,
            'cost_of_goods_sold': cost_of_goods,
            'total_expenses': total_expenses,
            'operating_income': get('operating_income', 'operating_profit', 'native_operating_income', 'screener_operating_profit'),
            'cash_and_equivalents': get('cash_and_equivalents', 'native_cash_and_equivalents'),
            'short_term_debt': get('short_term_debt'),
            'gross_profit': get('gross_profit', 'native_gross_profit'),
        }

    def get_earnings_history(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        n_quarters: int = 12,
        safety_lag_days: int = 0,
        date_field: str = 'announcement_date',
    ) -> Dict[str, list[dict]]:
        """Return PIT-safe quarterly earnings history keyed by ticker."""
        panel = self._load_factor_panel(frequency='quarterly')
        if panel.empty or 'ticker' not in panel.columns:
            return {}

        work = panel.copy()
        normalized_tickers = None
        if tickers:
            normalized_tickers = [self._normalize_ticker(t) for t in tickers]
            work = work[work['ticker'].isin(normalized_tickers)]

        if 'availability_date' in work.columns:
            availability = pd.to_datetime(work['availability_date'], errors='coerce') + timedelta(days=int(max(0, safety_lag_days)))
        else:
            availability = pd.to_datetime(work.get('quarter_end'), errors='coerce') + timedelta(days=int(self.reporting_lags.get('quarterly_results', 60) + max(0, safety_lag_days)))
        work['announcement_date'] = availability
        work = work[work['announcement_date'] <= pd.Timestamp(as_of_date)]
        work = work.sort_values(['ticker', 'announcement_date', 'quarter_end'], kind='mergesort')

        out: Dict[str, list[dict]] = {}
        for ticker, grp in work.groupby('ticker', sort=False):
            hist = []
            for _, row in grp.tail(int(max(1, n_quarters))).iterrows():
                record = row.to_dict()
                hist.append(
                    {
                        'ticker': str(ticker),
                        'quarter': record.get('quarter'),
                        'period_end': pd.to_datetime(record.get('quarter_end'), errors='coerce'),
                        'announcement_date': pd.to_datetime(record.get('announcement_date'), errors='coerce'),
                        'eps_actual': self._pick_first(record, 'eps', 'eps_in_rs'),
                        'revenue': self._pick_first(record, 'revenue', 'sales'),
                        'net_profit': self._pick_first(record, 'net_profit', 'net_income'),
                    }
                )
            out[str(ticker)] = hist

        if normalized_tickers is not None:
            for ticker in normalized_tickers:
                out.setdefault(ticker, [])
        return out

    def load_earnings_history(self, as_of_date: datetime, **kwargs) -> Dict[str, list[dict]]:
        """Backward-compatible alias for factor-facing quarterly earnings history."""
        return self.get_earnings_history(as_of_date, **kwargs)

    def get_free_float(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
    ) -> Dict[str, dict]:
        """Return latest PIT-safe promoter/free-float snapshot per ticker."""
        share = self._load_factor_panel(frequency='shareholding')
        annual = self.get_factor_financials(as_of_date, tickers=tickers, frequency='annual', periods=1)
        if share.empty or 'ticker' not in share.columns:
            return {}

        work = share.copy()
        normalized_tickers = None
        if tickers:
            normalized_tickers = [self._normalize_ticker(t) for t in tickers]
            work = work[work['ticker'].isin(normalized_tickers)]
        if 'availability_date' in work.columns:
            work = work[work['availability_date'] <= pd.Timestamp(as_of_date)]
        work = work.sort_values(['ticker', 'availability_date', 'quarter_end'], kind='mergesort')

        prices = None
        try:
            price_path = Path('data/processed/prices.parquet')
            if price_path.exists():
                prices = pd.read_parquet(price_path)
                if 'ticker' in prices.columns:
                    prices['ticker'] = prices['ticker'].map(self._normalize_ticker)
                if 'Date' in prices.columns:
                    prices['Date'] = pd.to_datetime(prices['Date'], errors='coerce')
                    prices = prices[prices['Date'] <= pd.Timestamp(as_of_date)]
                    prices = prices.sort_values(['ticker', 'Date'], kind='mergesort').groupby('ticker', sort=False).tail(1)
        except Exception:
            prices = None

        out: Dict[str, dict] = {}
        for ticker, grp in work.groupby('ticker', sort=False):
            row = grp.tail(1).iloc[0].to_dict()
            promoter_pct = self._pick_first(row, 'promoter_pct') or 0.0
            free_float_pct = self._pick_first(row, 'free_float_pct')
            if pd.isna(free_float_pct) or free_float_pct is None:
                free_float_pct = max(0.0, 100.0 - float(promoter_pct or 0.0))
            fin = annual.get(str(ticker), {}).get('current', {})
            shares_outstanding = self._pick_first(fin, 'shares_outstanding')
            free_float_shares = None
            if shares_outstanding is not None and pd.notna(shares_outstanding):
                free_float_shares = float(shares_outstanding) * (float(free_float_pct) / 100.0)
            market_cap = None
            if prices is not None and shares_outstanding is not None:
                px_row = prices[prices['ticker'] == str(ticker)]
                if not px_row.empty:
                    close_val = self._pick_first(px_row.iloc[0].to_dict(), 'Close', 'close')
                    if close_val is not None and pd.notna(close_val):
                        market_cap = float(close_val) * float(shares_outstanding)
            out[str(ticker)] = {
                'ticker': str(ticker),
                'availability_date': pd.to_datetime(row.get('availability_date'), errors='coerce'),
                'promoter_pct': float(promoter_pct or 0.0),
                'free_float_pct': float(free_float_pct or 0.0),
                'shares_outstanding': shares_outstanding,
                'free_float_shares': free_float_shares,
                'market_cap': market_cap,
            }

        if normalized_tickers is not None:
            for ticker in normalized_tickers:
                out.setdefault(ticker, {})
        return out

    def load_free_float(self, as_of_date: datetime, **kwargs) -> Dict[str, dict]:
        """Backward-compatible alias for free-float lookup."""
        return self.get_free_float(as_of_date, **kwargs)
    
    def _load_annual_financials(
        self,
        tickers: Optional[List[str]],
        statement_type: str
    ) -> pd.DataFrame:
        """Load annual financial statements."""
        try:
            # Try processed file first
            annual_path = Path(self.paths_config.get(
                'screener_fundamentals',
                'data/processed/screener_fundamentals_annual.csv'
            ))
            
            if annual_path.exists():
                df = pd.read_csv(annual_path)
                
                # Standardize column names
                if 'ticker' in df.columns:
                    df = df.rename(columns={'ticker': 'Ticker'})
                
                # Filter by tickers
                if tickers and 'Ticker' in df.columns:
                    df = df[df['Ticker'].isin(tickers)]
                
                # Handle date columns - fiscal_year to ReportDate
                if 'fiscal_year' in df.columns:
                    # Convert fiscal year to date (assume March 31 year end for Indian companies)
                    df['ReportDate'] = pd.to_datetime(df['fiscal_year'].astype(str) + '-03-31', errors='coerce')
                
                # Use availability_date if present, otherwise compute
                if 'availability_date' in df.columns:
                    df['AvailabilityDate'] = pd.to_datetime(df['availability_date'], errors='coerce')
                
                return df
            
            # Fall back to raw files
            raw_dir = Path(self.paths_config.get(
                'screener_financials',
                'data/raw/vendors/screener/financials'
            ))
            
            if not raw_dir.exists():
                raise DataNotFoundError(f"Screener financials directory not found: {raw_dir}")
            
            return self._load_from_raw_screener(raw_dir, tickers, statement_type, 'annual')
            
        except Exception as e:
            logger.error(f"Error loading annual financials: {e}")
            return pd.DataFrame()
    
    def _load_quarterly_financials(
        self,
        tickers: Optional[List[str]],
        statement_type: str
    ) -> pd.DataFrame:
        """Load quarterly financial statements."""
        try:
            quarterly_path = Path(self.paths_config.get(
                'screener_quarterly',
                'data/processed/screener_fundamentals_quarterly.csv'
            ))
            
            if quarterly_path.exists():
                df = pd.read_csv(quarterly_path)
                
                if tickers and 'Ticker' in df.columns:
                    df = df[df['Ticker'].isin(tickers)]
                
                if statement_type != 'all' and 'StatementType' in df.columns:
                    df = df[df['StatementType'] == statement_type]
                
                return df
            
            # Fall back to raw files
            raw_dir = Path(self.paths_config.get(
                'screener_financials',
                'data/raw/vendors/screener/financials'
            ))
            
            return self._load_from_raw_screener(raw_dir, tickers, statement_type, 'quarterly')
            
        except Exception as e:
            logger.error(f"Error loading quarterly financials: {e}")
            return pd.DataFrame()
    
    def _load_from_raw_screener(
        self,
        raw_dir: Path,
        tickers: Optional[List[str]],
        statement_type: str,
        frequency: str
    ) -> pd.DataFrame:
        """Load from raw Screener.in files."""
        if not raw_dir.exists():
            return pd.DataFrame()
        
        dfs = []
        
        # Map statement types to file suffixes
        suffix_map = {
            'balance_sheet': '_bs',
            'income_statement': '_pl',
            'cash_flow': '_cf',
        }
        
        # Determine which files to load
        if statement_type == 'all':
            suffixes = list(suffix_map.values())
        else:
            suffixes = [suffix_map.get(statement_type, '')]
        
        # Iterate through ticker directories
        for ticker_dir in raw_dir.iterdir():
            if not ticker_dir.is_dir():
                continue
            
            ticker = ticker_dir.name
            
            if tickers and ticker not in tickers:
                continue
            
            for suffix in suffixes:
                file_pattern = f"{ticker}_{frequency}{suffix}.csv"
                file_path = ticker_dir / file_pattern
                
                if not file_path.exists():
                    continue
                
                try:
                    ticker_df = pd.read_csv(file_path)
                    ticker_df['Ticker'] = ticker
                    ticker_df['StatementType'] = next(
                        (k for k, v in suffix_map.items() if v == suffix),
                        'unknown'
                    )
                    dfs.append(ticker_df)
                except Exception as e:
                    logger.warning(f"Error loading {file_path}: {e}")
        
        if not dfs:
            return pd.DataFrame()
        
        return pd.concat(dfs, ignore_index=True)
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize column names based on config mappings."""
        # Get column mappings from config
        column_map = self.config.get('financial_column_mappings', {})
        
        if not column_map:
            return df
        
        # Apply mappings
        df = df.rename(columns=column_map)
        
        return df
    
    def load_ratios(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        financials_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Load pre-computed financial ratios with PIT enforcement.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            financials_df: Pre-loaded financials to avoid double-loading
            
        Returns:
            DataFrame with financial ratios
        """
        # If financials not provided, load them
        if financials_df is None:
            financials_df = self.load_financials(as_of_date, tickers, frequency='annual')
        
        if financials_df.empty:
            return pd.DataFrame()
        
        # Compute ratios if not already present
        df = financials_df.copy()
        
        # Reset index for computation
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index()
        
        # Compute common ratios
        if 'NetIncome' in df.columns and 'Revenue' in df.columns:
            df['NetMargin'] = df['NetIncome'] / df['Revenue']
        
        if 'EBITDA' in df.columns and 'Revenue' in df.columns:
            df['EBITDAMargin'] = df['EBITDA'] / df['Revenue']
        
        if 'NetIncome' in df.columns and 'Equity' in df.columns:
            df['ROE'] = df['NetIncome'] / df['Equity']
        
        if 'EBIT' in df.columns and 'TotalAssets' in df.columns:
            df['ROA'] = df['EBIT'] / df['TotalAssets']
        
        if 'TotalDebt' in df.columns and 'Equity' in df.columns:
            df['DebtToEquity'] = df['TotalDebt'] / df['Equity']
        
        if 'CurrentAssets' in df.columns and 'CurrentLiabilities' in df.columns:
            df['CurrentRatio'] = df['CurrentAssets'] / df['CurrentLiabilities']
        
        return df
    
    def load_shareholding(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load shareholding patterns with PIT enforcement.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            
        Returns:
            DataFrame with (Ticker, QuarterEndDate, AvailabilityDate) as index
        """
        start_time = pd.Timestamp.now()
        
        # Normalize tickers - add .NS suffix if not present
        if tickers:
            normalized_tickers = []
            for ticker in tickers:
                if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                    normalized_tickers.append(f"{ticker}.NS")
                else:
                    normalized_tickers.append(ticker)
            tickers = normalized_tickers
        
        # Shareholding lag
        lag_days = self.reporting_lags.get('shareholding_pattern', 21)
        
        try:
            shareholding_path = Path(self.paths_config.get(
                'screener_shareholding',
                'data/processed/screener_shareholding.csv'
            ))
            
            if not shareholding_path.exists():
                logger.warning("Shareholding data not found")
                return pd.DataFrame()
            
            df = pd.read_csv(shareholding_path)
            
            # Standardize column names
            if 'ticker' in df.columns:
                df = df.rename(columns={'ticker': 'Ticker'})
            
            # Filter by tickers
            if tickers and 'Ticker' in df.columns:
                df = df[df['Ticker'].isin(tickers)]
            
            # Handle quarter column - convert Q1-2023 format to date
            if 'quarter' in df.columns:
                # Parse quarter strings like "Q1-2023" to dates
                def parse_quarter(q_str):
                    try:
                        parts = str(q_str).split('-')
                        if len(parts) == 2:
                            quarter = parts[0]
                            year = int(parts[1])
                            
                            # Map quarter to month end
                            quarter_map = {
                                'Q1': (year, 3, 31),   # Jan-Mar
                                'Q2': (year, 6, 30),   # Apr-Jun
                                'Q3': (year, 9, 30),   # Jul-Sep
                                'Q4': (year, 12, 31),  # Oct-Dec
                            }
                            
                            if quarter in quarter_map:
                                y, m, d = quarter_map[quarter]
                                return pd.Timestamp(year=y, month=m, day=d)
                    except:
                        pass
                    return pd.NaT
                
                df['QuarterEndDate'] = df['quarter'].apply(parse_quarter)
            elif 'QuarterEndDate' not in df.columns:
                date_cols = [c for c in df.columns if 'date' in c.lower() or 'quarter' in c.lower()]
                if date_cols:
                    df = df.rename(columns={date_cols[0]: 'QuarterEndDate'})
                    df['QuarterEndDate'] = pd.to_datetime(df['QuarterEndDate'], errors='coerce')
                else:
                    logger.error("No date column in shareholding data")
                    return pd.DataFrame()
            
            # Use availability_date if present, otherwise compute
            if 'availability_date' in df.columns:
                df['AvailabilityDate'] = pd.to_datetime(df['availability_date'], errors='coerce')
            else:
                df['AvailabilityDate'] = df['QuarterEndDate'] + timedelta(days=lag_days)
            
            # PIT enforcement
            df = df[df['AvailabilityDate'] <= as_of_date].copy()
            self._validate_pit(df, 'AvailabilityDate', as_of_date)
            
            # Set index
            if 'Ticker' in df.columns:
                df = df.set_index(['Ticker', 'QuarterEndDate', 'AvailabilityDate'])
            
            elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000
            self._log_load(len(df), len(df.columns), "shareholding", elapsed_ms, as_of_date)
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading shareholding data: {e}")
            return pd.DataFrame()
    
    def get_latest_available_filing(
        self,
        ticker: str,
        as_of_date: datetime,
        statement_type: str = 'all'
    ) -> pd.Series:
        """
        Get the most recent financial filing available as of a date.
        
        Args:
            ticker: Ticker symbol
            as_of_date: Point-in-time date
            statement_type: Type of statement to retrieve
            
        Returns:
            Series with the latest filing data
        """
        df = self.load_financials(
            as_of_date=as_of_date,
            tickers=[ticker],
            statement_type=statement_type,
            frequency='annual'
        )
        
        if df.empty:
            return pd.Series()
        
        # Get the most recent filing
        df = df.reset_index()
        df = df.sort_values('AvailabilityDate', ascending=False)
        
        return df.iloc[0]
    def load_credit_ratings_for_fundamentals(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load credit ratings as part of fundamental analysis.
        
        This delegates to AlternativeDataLoader but provides a unified interface
        for fundamental analysis that includes credit distress signals.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            
        Returns:
            DataFrame with latest credit rating per ticker
        """
        try:
            # Import here to avoid circular dependency
            from .alternative_loader import AlternativeDataLoader
            
            alt_loader = AlternativeDataLoader(self.config)
            ratings_df = alt_loader.load_credit_ratings(as_of_date, tickers)
            
            if ratings_df.empty:
                logger.warning("No credit ratings data available")
                return pd.DataFrame()
            
            # Get latest rating per ticker
            if isinstance(ratings_df.index, pd.MultiIndex):
                ratings_df = ratings_df.reset_index()
            
            if 'Ticker' in ratings_df.columns and 'ActionDate' in ratings_df.columns:
                # Sort and get most recent
                ratings_df = ratings_df.sort_values(['Ticker', 'ActionDate'], ascending=[True, False])
                latest_ratings = ratings_df.groupby('Ticker').first().reset_index()
                
                # Keep only relevant columns for fundamental analysis
                keep_cols = ['Ticker', 'CurrentRating', 'in_distress', 'rating_momentum', 'ActionDate']
                keep_cols = [c for c in keep_cols if c in latest_ratings.columns]
                latest_ratings = latest_ratings[keep_cols]
                
                return latest_ratings
            
            return ratings_df
            
        except Exception as e:
            logger.error(f"Error loading credit ratings for fundamentals: {e}")
            return pd.DataFrame()
