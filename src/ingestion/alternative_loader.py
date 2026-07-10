"""
AlternativeDataLoader — Load alternative data sources with PIT enforcement.

Data sources:
- GST: data/processed/gst_monthly.parquet
- Power consumption: data/processed/power_consumption.parquet
- Credit ratings: data/processed/alternative/credit_ratings_nse_all.csv
- Bulk deals: data/processed/alternative/bulk_deals_nse_all.csv
- Promoter pledges: data/processed/alternative/promoter_pledge_all.csv

This is the first production-grade reader for these data sources.
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
from pandas.tseries.offsets import BDay

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


class AlternativeDataLoader(BaseLoader):
    """Loads alternative data sources with standardized PIT handling."""

    _BULK_HISTORY_PATHS = (
        'data/canonical/alternative/bulk_deals_nse_all.parquet',
        'data/canonical/alternative/bulk_deals_nse_all.csv',
        'data/processed/alternative/bulk_deals_nse_all.parquet',
        'data/processed/alternative/bulk_deals_nse_all.csv',
        'data/processed/alternative/bulk_deals_nse_recent.csv',
    )
    _PLEDGE_HISTORY_PATHS = (
        'data/canonical/alternative/promoter_pledge_all.parquet',
        'data/canonical/alternative/promoter_pledge_all.csv',
        'data/processed/alternative/promoter_pledge_all.parquet',
        'data/processed/alternative/promoter_pledge_all.csv',
    )
    
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        """
        Load alternative data (delegates to load_all_alternative).
        
        Args:
            as_of_date: Point-in-time date
            **kwargs: Additional parameters
            
        Returns:
            Dict of DataFrames (converted to single DataFrame for compatibility)
        """
        # Return GST as default, or all as dict
        return self.load_gst(as_of_date, **kwargs)

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

    def _read_first_existing_table(self, paths: tuple[str, ...]) -> pd.DataFrame:
        for raw_path in paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            try:
                if path.suffix == '.parquet':
                    return pd.read_parquet(path)
                if path.suffix == '.csv':
                    return pd.read_csv(path)
            except Exception as exc:
                logger.warning("Failed reading %s: %s", path, exc)
        return pd.DataFrame()

    def _load_pit_universe_history(self) -> pd.DataFrame:
        universe_path = Path(
            self.paths_config.get(
                'nse_universe_history',
                'data/reference/nse_universe_history.parquet',
            )
        )
        if not universe_path.exists():
            return pd.DataFrame()
        try:
            history = pd.read_parquet(universe_path)
        except Exception as exc:
            logger.warning("Failed reading PIT universe history %s: %s", universe_path, exc)
            return pd.DataFrame()
        if history.empty or not {'date', 'ticker'}.issubset(set(history.columns)):
            return pd.DataFrame()
        history = history.copy()
        history['date'] = pd.to_datetime(history['date'], errors='coerce').dt.normalize()
        history['ticker'] = history['ticker'].map(self._normalize_ticker)
        if 'tradeable' in history.columns:
            history = history[history['tradeable'].fillna(False)]
        elif 'available' in history.columns:
            history = history[history['available'].fillna(False)]
        history = history.dropna(subset=['date', 'ticker'])
        return history[['date', 'ticker']].drop_duplicates(ignore_index=True)

    def get_bulk_deal_history(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        lookback_days: int = 63,
        safety_lag_days: int = 1,
        apply_pit_universe_filter: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Return PIT-safe raw bulk-deal events keyed by ticker for factor construction."""
        frame = self._read_first_existing_table(self._BULK_HISTORY_PATHS)
        normalized_tickers = [self._normalize_ticker(t) for t in tickers] if tickers else None
        if frame.empty:
            return {ticker: pd.DataFrame() for ticker in (normalized_tickers or [])}

        work = frame.copy()
        rename_map = {}
        if 'nse_ticker' in work.columns and 'ticker' not in work.columns:
            rename_map['nse_ticker'] = 'ticker'
        if 'TradeDate' in work.columns and 'date' not in work.columns:
            rename_map['TradeDate'] = 'date'
        if 'deal_type' not in work.columns and 'DealType' in work.columns:
            rename_map['DealType'] = 'deal_type'
        if 'quantity' not in work.columns and 'Quantity' in work.columns:
            rename_map['Quantity'] = 'quantity'
        if 'price' not in work.columns and 'Price' in work.columns:
            rename_map['Price'] = 'price'
        if 'client_name' not in work.columns and 'clientName' in work.columns:
            rename_map['clientName'] = 'client_name'
        if rename_map:
            work = work.rename(columns=rename_map)

        work['ticker'] = work.get('ticker', '').map(self._normalize_ticker)
        work['date'] = pd.to_datetime(work.get('date'), errors='coerce')
        work['availability_date'] = pd.to_datetime(work.get('availability_date'), errors='coerce')
        if work['availability_date'].isna().all():
            work['availability_date'] = pd.to_datetime(work['date'], errors='coerce') + BDay(int(max(1, safety_lag_days)))
        else:
            lagged = pd.to_datetime(work['date'], errors='coerce') + BDay(int(max(1, safety_lag_days)))
            work['availability_date'] = pd.concat([work['availability_date'], lagged], axis=1).max(axis=1)

        work['quantity'] = pd.to_numeric(work.get('quantity'), errors='coerce')
        work['price'] = pd.to_numeric(work.get('price'), errors='coerce')
        work['deal_type'] = work.get('deal_type', '').astype(str).str.upper().str.strip()
        work['client_name'] = work.get('client_name', pd.Series('', index=work.index)).astype(str).fillna('')
        work['signed_qty'] = np.where(work['deal_type'].eq('SELL'), -work['quantity'], work['quantity'])
        work['notional'] = pd.to_numeric(work.get('notional'), errors='coerce')
        if work['notional'].isna().all():
            work['notional'] = work['quantity'] * work['price']

        work = work.dropna(subset=['date', 'ticker', 'availability_date']).copy()
        start_date = pd.Timestamp(as_of_date) - timedelta(days=int(max(lookback_days, 1) + 7))
        work = work[
            (work['availability_date'] <= pd.Timestamp(as_of_date))
            & (work['date'] >= start_date)
        ].copy()

        if normalized_tickers is not None:
            work = work[work['ticker'].isin(normalized_tickers)]

        if apply_pit_universe_filter:
            history = self._load_pit_universe_history()
            if not history.empty:
                covered_min = history['date'].min()
                covered_max = history['date'].max()
                work['event_date'] = work['date'].dt.normalize()
                covered = work['event_date'].between(covered_min, covered_max)
                keep_mask = pd.Series(True, index=work.index, dtype=bool)
                if covered.any():
                    allowed_keys = pd.Index(
                        history['date'].dt.strftime('%Y-%m-%d') + '|' + history['ticker']
                    )
                    subset = work.loc[covered, ['event_date', 'ticker']].copy()
                    subset_keys = subset['event_date'].dt.strftime('%Y-%m-%d') + '|' + subset['ticker']
                    keep_mask.loc[covered] = subset_keys.isin(allowed_keys).to_numpy(dtype=bool)
                work = work[keep_mask].copy()
                work = work.drop(columns=['event_date'], errors='ignore')

        work = work.sort_values(['ticker', 'availability_date', 'date'], kind='mergesort')
        out: Dict[str, pd.DataFrame] = {}
        for ticker, grp in work.groupby('ticker', sort=False):
            out[str(ticker)] = grp.reset_index(drop=True)
        if normalized_tickers is not None:
            for ticker in normalized_tickers:
                out.setdefault(ticker, pd.DataFrame(columns=work.columns))
        return out

    def load_bulk_deal_history(self, as_of_date: datetime, **kwargs) -> Dict[str, pd.DataFrame]:
        """Backward-compatible alias for raw bulk deal history."""
        return self.get_bulk_deal_history(as_of_date, **kwargs)

    def get_promoter_pledge_history(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        safety_lag_days: int = 25,
    ) -> Dict[str, pd.DataFrame]:
        """Return PIT-safe raw promoter-pledge history keyed by ticker."""
        frame = self._read_first_existing_table(self._PLEDGE_HISTORY_PATHS)
        normalized_tickers = [self._normalize_ticker(t) for t in tickers] if tickers else None
        if frame.empty:
            return {ticker: pd.DataFrame() for ticker in (normalized_tickers or [])}

        work = frame.copy()
        rename_map = {}
        if 'nse_ticker' in work.columns and 'ticker' not in work.columns:
            rename_map['nse_ticker'] = 'ticker'
        if 'date' in work.columns and 'quarter_end' not in work.columns:
            rename_map['date'] = 'quarter_end'
        if 'QuarterEnd' in work.columns and 'quarter_end' not in work.columns:
            rename_map['QuarterEnd'] = 'quarter_end'
        if rename_map:
            work = work.rename(columns=rename_map)

        work['ticker'] = work.get('ticker', '').map(self._normalize_ticker)
        work['quarter_end'] = pd.to_datetime(work.get('quarter_end'), errors='coerce')
        work['broadcast_datetime'] = pd.to_datetime(work.get('broadcast_datetime'), errors='coerce')
        work['availability_date'] = pd.to_datetime(work.get('availability_date'), errors='coerce')
        lagged = pd.to_datetime(work['quarter_end'], errors='coerce') + timedelta(days=int(max(0, safety_lag_days)))
        if work['availability_date'].isna().all():
            work['availability_date'] = lagged
        else:
            work['availability_date'] = pd.concat([work['availability_date'], lagged], axis=1).max(axis=1)
        work['pledge_pct'] = pd.to_numeric(work.get('pledge_pct'), errors='coerce')
        if work['pledge_pct'].isna().all() and {'shares_pledged', 'total_promoter_shares'}.issubset(set(work.columns)):
            pledged = pd.to_numeric(work.get('shares_pledged'), errors='coerce')
            total = pd.to_numeric(work.get('total_promoter_shares'), errors='coerce').replace(0.0, np.nan)
            work['pledge_pct'] = 100.0 * pledged / total

        work = work.dropna(subset=['ticker', 'quarter_end', 'availability_date']).copy()
        work = work[work['availability_date'] <= pd.Timestamp(as_of_date)].copy()
        if normalized_tickers is not None:
            work = work[work['ticker'].isin(normalized_tickers)]
        work = work.sort_values(['ticker', 'availability_date', 'quarter_end'], kind='mergesort')
        work = work.drop_duplicates(subset=['ticker', 'quarter_end'], keep='last')

        out: Dict[str, pd.DataFrame] = {}
        for ticker, grp in work.groupby('ticker', sort=False):
            out[str(ticker)] = grp.reset_index(drop=True)
        if normalized_tickers is not None:
            for ticker in normalized_tickers:
                out.setdefault(ticker, pd.DataFrame(columns=work.columns))
        return out

    def load_promoter_pledge_history(self, as_of_date: datetime, **kwargs) -> Dict[str, pd.DataFrame]:
        """Backward-compatible alias for raw promoter-pledge history."""
        return self.get_promoter_pledge_history(as_of_date, **kwargs)
    
    def load_gst(
        self,
        as_of_date: datetime,
        level: str = 'national'
    ) -> pd.DataFrame:
        """
        Load GST data with derived features.
        
        Args:
            as_of_date: Point-in-time date
            level: 'national' or 'state'
            
        Returns:
            DataFrame with MonthEnd as index and GST metrics
        """
        try:
            def _normalize_gst_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
                frame = raw_df.copy()
                date_col = next((c for c in ['date', 'MonthEnd', 'month_end', 'year_month'] if c in frame.columns), None)
                if not date_col:
                    return pd.DataFrame()
                if date_col == 'year_month':
                    frame['MonthEnd'] = pd.to_datetime(frame[date_col].astype(str) + '-01', errors='coerce') + pd.offsets.MonthEnd(0)
                else:
                    frame['MonthEnd'] = pd.to_datetime(frame[date_col], errors='coerce')

                if 'availability_date' in frame.columns:
                    frame['ReleaseDate'] = pd.to_datetime(frame['availability_date'], errors='coerce')
                elif 'ReleaseDate' in frame.columns:
                    frame['ReleaseDate'] = pd.to_datetime(frame['ReleaseDate'], errors='coerce')
                elif 'release_date' in frame.columns:
                    frame['ReleaseDate'] = pd.to_datetime(frame['release_date'], errors='coerce')
                else:
                    frame['ReleaseDate'] = frame['MonthEnd'] + timedelta(days=15)

                return frame

            gst_candidates = [
                self.paths_config.get('gst'),
                'data/processed/macro/gst_ewaybill_monthly.parquet',
                'data/processed/gst_monthly.parquet',
            ]
            unique_candidates: list[Path] = []
            for raw_path in gst_candidates:
                if not raw_path:
                    continue
                candidate = Path(raw_path)
                if candidate.exists() and candidate not in unique_candidates:
                    unique_candidates.append(candidate)
            gst_path = None
            freshest_release = pd.Timestamp.min
            freshest_period = pd.Timestamp.min
            for candidate in unique_candidates:
                try:
                    candidate_df = pd.read_parquet(candidate) if candidate.suffix == '.parquet' else pd.read_csv(candidate)
                except Exception:
                    continue
                candidate_df = _normalize_gst_frame(candidate_df)
                if candidate_df.empty:
                    continue
                latest_period = pd.to_datetime(candidate_df['MonthEnd'], errors='coerce').max()
                latest_release = pd.to_datetime(candidate_df['ReleaseDate'], errors='coerce').max()
                if (latest_release, latest_period) >= (freshest_release, freshest_period):
                    freshest_release = latest_release
                    freshest_period = latest_period
                    gst_path = candidate

            if gst_path is None:
                logger.warning("GST data not found")
                return self._empty_gst_schema()
            
            df = pd.read_parquet(gst_path)
            df = _normalize_gst_frame(df)
            if len(df) < 12:
                supplemental_frames = []
                for candidate in unique_candidates:
                    if candidate == gst_path:
                        continue
                    try:
                        extra_df = pd.read_parquet(candidate) if candidate.suffix == '.parquet' else pd.read_csv(candidate)
                    except Exception:
                        continue
                    extra_df = _normalize_gst_frame(extra_df)
                    if not extra_df.empty:
                        supplemental_frames.append(extra_df)
                if supplemental_frames:
                    df = pd.concat([df, *supplemental_frames], ignore_index=True, sort=False)

            if 'MonthEnd' not in df.columns:
                logger.error("No date column in GST data")
                return self._empty_gst_schema()

            dedupe_keys = ['MonthEnd']
            for column in ['state', 'category']:
                if column in df.columns:
                    dedupe_keys.append(column)
            df = df.sort_values(['MonthEnd', 'ReleaseDate'], kind='mergesort')
            df = df.drop_duplicates(subset=dedupe_keys, keep='last')

            # PIT enforcement
            df = df[df['ReleaseDate'] <= as_of_date].copy()
            self._validate_pit(df, 'ReleaseDate', as_of_date)

            # Honour the `level` argument. The chosen source may be STATE-level
            # (a 'state' column with many rows per month); computing MoM/YoY
            # pct_change on that interleaved frame mixes states and is meaningless
            # (the old code ignored `level` entirely). For 'national' we collapse
            # states to one monthly series (sum values per MonthEnd) before
            # deriving features; for 'state' we derive features per state.
            if 'state' in df.columns and str(level).lower() == 'national':
                num_cols = [c for c in df.columns
                            if c not in ('MonthEnd', 'state', 'category', 'ReleaseDate')
                            and pd.api.types.is_numeric_dtype(df[c])]
                release = df.groupby('MonthEnd')['ReleaseDate'].max().reset_index()
                df = df.groupby('MonthEnd', as_index=False)[num_cols].sum().merge(release, on='MonthEnd')
                df = self._compute_gst_features(df)
            elif 'state' in df.columns:  # per-state features
                parts = []
                for _, grp in df.sort_values('MonthEnd').groupby('state', sort=False):
                    parts.append(self._compute_gst_features(grp.copy()))
                df = pd.concat(parts, ignore_index=True) if parts else df
            else:
                df = self._compute_gst_features(df)

            df = df.set_index('MonthEnd')

            return df
            
        except Exception as e:
            logger.error(f"Error loading GST data: {e}")
            return self._empty_gst_schema()
    
    def _compute_gst_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute GST derived features."""
        if 'gst_collection' not in df.columns:
            # Bind gst_collection to a rupee VALUE column, deterministically.
            # The old `gst_cols[0]` picked the first keyword match in column order,
            # which could latch onto a COUNT series (eway_bills_generated) instead
            # of the value — silently turning the GST signal into a bill count.
            priority = [
                'gst_collection', 'gross_gst_collection', 'gst_revenue', 'total_gst',
                'eway_bill_value_crore', 'eway_bill_value_cr', 'eway_bill_value',
            ]
            chosen = next((c for c in priority if c in df.columns), None)
            if chosen is None:
                # Any gst/collection/value column that is NOT a count.
                chosen = next(
                    (c for c in df.columns
                     if ('gst' in c.lower() or 'collection' in c.lower() or 'value' in c.lower())
                     and not any(tok in c.lower() for tok in ('count', 'generated', 'number', 'num_'))),
                    None,
                )
            if chosen:
                df = df.rename(columns={chosen: 'gst_collection'})
        
        if 'gst_collection' in df.columns:
            df = df.sort_values('MonthEnd')
            
            # Month-over-month growth
            df['gst_mom_growth'] = df['gst_collection'].pct_change()
            
            # Year-over-year growth
            df['gst_yoy_growth'] = df['gst_collection'].pct_change(12)
            
            # 3-month moving average
            df['gst_3m_ma'] = df['gst_collection'].rolling(3).mean()
            
            # Deviation from 12-month trend
            df['gst_12m_trend'] = df['gst_collection'].rolling(12).mean()
            df['gst_deviation_from_trend'] = (df['gst_collection'] - df['gst_12m_trend']) / df['gst_12m_trend']
        
        return df
    
    def _empty_gst_schema(self) -> pd.DataFrame:
        """Return empty DataFrame with correct GST schema."""
        return pd.DataFrame(columns=[
            'gst_collection', 'gst_mom_growth', 'gst_yoy_growth',
            'gst_3m_ma', 'gst_deviation_from_trend'
        ])
    
    def load_power_consumption(self, as_of_date: datetime) -> pd.DataFrame:
        """
        Load power consumption data with seasonal adjustments.

        Data source: NPP DGR-17 daily power supply data
        Columns: date, region, energy_met_mu, peak_met_gw, energy_requirement_mu, 
                 deficit_pct, availability_date, source

        Args:
            as_of_date: Point-in-time date

        Returns:
            DataFrame with power consumption metrics
        """
        try:
            power_path = Path(self.paths_config.get('power', 'data/processed/macro/cea_power_daily.parquet'))

            if not power_path.exists():
                logger.warning("Power consumption data not found")
                return pd.DataFrame()

            df = pd.read_parquet(power_path)

            # Standardize column names
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'Date'})
            if 'availability_date' in df.columns:
                df = df.rename(columns={'availability_date': 'AvailabilityDate'})
            if 'energy_met_mu' in df.columns:
                df = df.rename(columns={'energy_met_mu': 'EnergyMetMU'})
            if 'peak_met_gw' in df.columns:
                df = df.rename(columns={'peak_met_gw': 'PeakMetGW'})
            if 'energy_requirement_mu' in df.columns:
                df = df.rename(columns={'energy_requirement_mu': 'EnergyRequirementMU'})
            if 'deficit_pct' in df.columns:
                df = df.rename(columns={'deficit_pct': 'DeficitPct'})

            # Convert dates
            df['Date'] = pd.to_datetime(df['Date'])
            if 'AvailabilityDate' in df.columns:
                df['AvailabilityDate'] = pd.to_datetime(df['AvailabilityDate'])

            # PIT enforcement - use availability_date if present, otherwise Date + 1 day
            if 'AvailabilityDate' in df.columns:
                df = df[df['AvailabilityDate'] <= as_of_date].copy()
                self._validate_pit(df, 'AvailabilityDate', as_of_date)
            else:
                df['AvailabilityDate'] = df['Date'] + timedelta(days=1)
                df = df[df['AvailabilityDate'] <= as_of_date].copy()
                self._validate_pit(df, 'AvailabilityDate', as_of_date)

            # Compute features
            df = self._compute_power_features(df)

            df = df.set_index('Date')

            return df

        except Exception as e:
            logger.error(f"Error loading power data: {e}")
            return pd.DataFrame()
    
    def _compute_power_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute power consumption features with seasonal adjustment."""
        if 'EnergyMetMU' in df.columns and 'Date' in df.columns:
            df = df.sort_values('Date')

            # MoM growth (using 30-day rolling for monthly comparison)
            df['power_mom_growth'] = df['EnergyMetMU'].pct_change(30)

            # YoY growth (using 365-day rolling for yearly comparison)
            df['power_yoy_growth'] = df['EnergyMetMU'].pct_change(365)

            # Trailing 1-year seasonal baseline. This is DAILY data, so a
            # "52-week" window is ~364 rows, not 52 — the old rolling(52) was a
            # 52-DAY median mislabelled as 52 weeks, so the deviation captured
            # ~2 months of trend rather than a full-year deseasonalised baseline.
            df['power_seasonal_baseline'] = df['EnergyMetMU'].rolling(364, min_periods=30).median()
            df['power_deviation_from_seasonal'] = (
                (df['EnergyMetMU'] - df['power_seasonal_baseline']) / df['power_seasonal_baseline']
            )

            # Deficit trend (if deficit_pct available)
            if 'DeficitPct' in df.columns:
                df['deficit_7d_ma'] = df['DeficitPct'].rolling(7, min_periods=1).mean()
                df['deficit_30d_ma'] = df['DeficitPct'].rolling(30, min_periods=1).mean()

        return df
    
    def load_credit_ratings(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load credit rating changes with momentum indicators.
        
        Uses NSE credit ratings data (processed from NSE CRD files).

        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)

        Returns:
            DataFrame with (Ticker, ActionDate) as index
        """
        try:
            # Try NSE processed credit ratings first (primary source)
            ratings_path = Path(
                self.paths_config.get(
                    'credit_ratings_nse',
                    self.paths_config.get(
                        'credit_ratings_processed',
                        'data/processed/alternative/credit_ratings_nse_all.csv',
                    ),
                )
            )
            
            # Fallback to old BSE path
            if not ratings_path.exists():
                ratings_path = Path(self.paths_config.get('credit_ratings', 
                                    'data/raw/shared/alternative/credit_ratings'))

            if not ratings_path.exists():
                logger.warning("Credit ratings data not found")
                return pd.DataFrame()

            # Load NSE credit ratings CSV
            if ratings_path.suffix == '.csv':
                df = pd.read_csv(ratings_path, low_memory=False)
                logger.info(f"Loaded {len(df):,} credit ratings from {ratings_path.name}")
            elif ratings_path.suffix == '.parquet':
                df = pd.read_parquet(ratings_path)
                logger.info(f"Loaded {len(df):,} credit ratings from {ratings_path.name}")
            elif ratings_path.is_dir():
                # Old BSE format - directory of CSVs
                csv_files = list(ratings_path.glob('*.csv'))
                if not csv_files:
                    logger.warning("No credit rating CSV files found")
                    return pd.DataFrame()

                dfs = []
                for csv_file in csv_files:
                    try:
                        df_temp = pd.read_csv(csv_file)
                        dfs.append(df_temp)
                    except Exception as e:
                        logger.warning(f"Error reading {csv_file}: {e}")

                if not dfs:
                    return pd.DataFrame()

                df = pd.concat(dfs, ignore_index=True)
                logger.info(f"Loaded {len(df):,} credit ratings from BSE files")
            else:
                logger.warning(f"Unknown credit ratings format: {ratings_path}")
                return pd.DataFrame()

            # Standardize column names for NSE CRD format
            # NSE CRD columns: company_name, date, IDENTIFIER, NAME OF CREDIT RATING AGENCY, 
            #                  CREDIT RATING, RATING ACTION, OUTLOOK, DATE OF CREDIT RATING
            if 'company_name' in df.columns:
                df = df.rename(columns={'company_name': 'CompanyName'})
            if 'nse_ticker' in df.columns:
                df = df.rename(columns={'nse_ticker': 'Ticker'})
            if 'symbol' in df.columns and 'Ticker' not in df.columns:
                df = df.rename(columns={'symbol': 'Ticker'})
            if 'IDENTIFIER' in df.columns:
                if 'Ticker' not in df.columns or df['Ticker'].isna().all():
                    identifier = df['IDENTIFIER'].astype(str).str.strip()
                    df['Ticker'] = identifier.replace({'': None, 'nan': None, 'None': None})
            if 'NAME OF CREDIT RATING AGENCY' in df.columns:
                df = df.rename(columns={'NAME OF CREDIT RATING AGENCY': 'Agency'})
            if 'agency' in df.columns and 'Agency' not in df.columns:
                df = df.rename(columns={'agency': 'Agency'})
            if 'CREDIT RATING' in df.columns:
                df = df.rename(columns={'CREDIT RATING': 'CurrentRating'})
            if 'rating' in df.columns and 'CurrentRating' not in df.columns:
                df = df.rename(columns={'rating': 'CurrentRating'})
            if 'RATING ACTION' in df.columns:
                df = df.rename(columns={'RATING ACTION': 'ActionType'})
            if 'rating_action' in df.columns and 'ActionType' not in df.columns:
                df = df.rename(columns={'rating_action': 'ActionType'})
            if 'OUTLOOK' in df.columns:
                df = df.rename(columns={'OUTLOOK': 'Outlook'})
            if 'outlook' in df.columns and 'Outlook' not in df.columns:
                df = df.rename(columns={'outlook': 'Outlook'})
            
            # Use DATE OF CREDIT RATING as the action date (not the generic 'date' column).
            # Parse with the expected dd-mm-YYYY format first, then fall back to a
            # general parse for any rows that don't match, and warn if a material
            # share still fails — the old rigid format + errors='coerce' turned
            # every off-format date into NaT that the PIT filter dropped SILENTLY.
            if 'DATE OF CREDIT RATING' in df.columns:
                raw_action = df['DATE OF CREDIT RATING']
                parsed = pd.to_datetime(raw_action, errors='coerce', format='%d-%m-%Y')
                fallback_mask = parsed.isna() & raw_action.notna()
                if fallback_mask.any():
                    parsed.loc[fallback_mask] = pd.to_datetime(
                        raw_action[fallback_mask], errors='coerce', dayfirst=True
                    )
                df['ActionDate'] = parsed
                still_bad = int((df['ActionDate'].isna() & raw_action.notna()).sum())
                if still_bad:
                    logger.warning("%d credit-rating rows have unparseable ActionDate (dropped by PIT filter)", still_bad)
            elif 'date' in df.columns:
                df['ActionDate'] = pd.to_datetime(df['date'], errors='coerce')

            if 'Ticker' in df.columns:
                ticker_series = df['Ticker'].astype(str).str.strip()
                ticker_series = ticker_series.replace({'': None, 'nan': None, 'None': None})
                ticker_series = ticker_series.where(
                    ticker_series.isna() | ticker_series.str.endswith(('.NS', '.BO')),
                    ticker_series + '.NS',
                )
                df['Ticker'] = ticker_series

            # Filter by tickers
            if tickers and 'Ticker' in df.columns and df['Ticker'].notna().any():
                normalized_tickers = []
                for ticker in tickers:
                    if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                        normalized_tickers.append(f"{ticker}.NS")
                    else:
                        normalized_tickers.append(ticker)
                df = df[df['Ticker'].isin(normalized_tickers)]

            # PIT enforcement
            if 'ActionDate' in df.columns:
                df = df[df['ActionDate'] <= as_of_date].copy()
                self._validate_pit(df, 'ActionDate', as_of_date)

                # Compute momentum indicators
                df = self._compute_rating_momentum(df)

                # Set index
                if 'Ticker' in df.columns and df['Ticker'].notna().any() and 'ActionDate' in df.columns:
                    df = df.set_index(['Ticker', 'ActionDate'])
                elif 'CompanyName' in df.columns:
                    df = df.set_index(['CompanyName', 'ActionDate'])
            elif 'Ticker' in df.columns and df['Ticker'].notna().any():
                df = df.set_index('Ticker')
            elif 'CompanyName' in df.columns:
                df = df.set_index('CompanyName')

            logger.info(f"Loaded {len(df):,} credit rating actions after filtering")
            return df

        except Exception as e:
            logger.error(f"Error loading credit ratings: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def _compute_rating_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute rating momentum indicators."""
        group_field = None
        if 'Ticker' in df.columns and df['Ticker'].notna().any():
            group_field = 'Ticker'
        elif 'CompanyName' in df.columns:
            group_field = 'CompanyName'

        if 'ActionType' in df.columns and group_field and 'ActionDate' in df.columns:
            df = df.sort_values([group_field, 'ActionDate'])
            
            # Normalize ActionType to uppercase for consistent matching
            df['ActionType'] = df['ActionType'].str.upper()
            
            # Net upgrades minus downgrades over trailing 90 days
            try:
                def compute_momentum(group):
                    """Compute momentum for a single ticker group."""
                    group = group.sort_values('ActionDate')
                    momentum = []
                    for i, row in group.iterrows():
                        # Trailing 90-day window ending AT this row's date. The
                        # window MUST be upper-bounded by row['ActionDate']: the
                        # old code used only `>= cutoff` with no upper bound, so a
                        # historical row's momentum counted FUTURE rating actions
                        # (look-ahead) — poisoning any point-in-time / backtest
                        # consumer of these rows.
                        cutoff_date = row['ActionDate'] - pd.Timedelta(days=90)
                        recent = group[
                            (group['ActionDate'] >= cutoff_date)
                            & (group['ActionDate'] <= row['ActionDate'])
                        ]
                        upgrades = (recent['ActionType'] == 'UPGRADE').sum()
                        downgrades = (recent['ActionType'] == 'DOWNGRADE').sum()
                        momentum.append(upgrades - downgrades)
                    group['rating_momentum'] = momentum
                    return group
                
                df = df.groupby(group_field, group_keys=False).apply(compute_momentum)
            except Exception as e:
                logger.warning(f"Could not compute rating momentum: {e}")
                df['rating_momentum'] = 0
            
            # Distress flag (rating below BBB-). NSE rating strings carry an
            # agency prefix/bracket ("CRISIL BB+", "[ICRA]B+", "IND A-"), so an
            # exact isin() against bare symbols matched almost nothing and left
            # in_distress ~always False. Extract the rating symbol first, then match.
            if 'CurrentRating' in df.columns:
                distress_ratings = {'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'C', 'D'}

                def _rating_symbol(value: object) -> str:
                    s = str(value or '').upper()
                    # strip agency brackets/prefixes; keep the last token that
                    # looks like a rating (letters A–D + optional +/-).
                    tokens = re.findall(r'[A-D]{1,3}[+-]?', s.replace('[', ' ').replace(']', ' '))
                    return tokens[-1] if tokens else ''

                df['in_distress'] = df['CurrentRating'].map(_rating_symbol).isin(distress_ratings)
        
        return df
    
    def load_bulk_deals(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        lookback_days: int = 90,
        nifty500_only: bool = False
    ) -> pd.DataFrame:
        """
        Load NSE bulk deal data with aggregated signals.
        
        Data source: NSE official bulk deals (BSE data removed)

        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            lookback_days: Days to aggregate over
            nifty500_only: If True, load only Nifty 500 filtered data

        Returns:
            DataFrame with aggregated bulk deal signals per ticker
        """
        try:
            # Use NSE data only (BSE data has been removed)
            if nifty500_only:
                bulk_path = Path(self.paths_config.get('bulk_deals_nifty500', 
                                    'data/processed/alternative/bulk_deals_nse_nifty500.csv'))
            else:
                bulk_path = Path(
                    self.paths_config.get(
                        'bulk_deals_nse',
                        self.paths_config.get('bulk_deals', 'data/processed/alternative/bulk_deals_nse_all.csv'),
                    )
                )
            
            # Fallback to NSE recent file
            if not bulk_path.exists():
                bulk_path = Path('data/processed/alternative/bulk_deals_nse_recent.csv')
            
            if not bulk_path.exists():
                logger.warning("NSE bulk deals data not found")
                return pd.DataFrame()

            # Load data
            if bulk_path.suffix == '.csv':
                df = pd.read_csv(bulk_path, parse_dates=['date'])
            else:
                df = pd.read_parquet(bulk_path)

            # Standardize column names
            if 'nse_ticker' in df.columns:
                df = df.rename(columns={'nse_ticker': 'Ticker'})
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'TradeDate'})
            if 'deal_type' in df.columns:
                df = df.rename(columns={'deal_type': 'DealType'})
            if 'quantity' in df.columns:
                df = df.rename(columns={'quantity': 'Quantity'})
            if 'price' in df.columns:
                df = df.rename(columns={'price': 'Price'})

            # Convert date
            if 'TradeDate' in df.columns:
                df['TradeDate'] = pd.to_datetime(df['TradeDate'], errors='coerce')
                df = df.dropna(subset=['TradeDate'])

            # Filter by tickers
            if tickers and 'Ticker' in df.columns:
                # Normalize tickers
                normalized_tickers = []
                for ticker in tickers:
                    if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                        normalized_tickers.append(f"{ticker}.NS")
                    else:
                        normalized_tickers.append(ticker)
                df = df[df['Ticker'].isin(normalized_tickers)]

            # PIT enforcement (1-day lag for bulk deal reporting)
            if 'TradeDate' in df.columns:
                df['AvailabilityDate'] = df['TradeDate'] + timedelta(days=1)
                df = df[df['AvailabilityDate'] <= as_of_date].copy()
                self._validate_pit(df, 'AvailabilityDate', as_of_date)

                # Filter to lookback period
                start_date = as_of_date - timedelta(days=lookback_days)
                df = df[df['TradeDate'] >= start_date]

                # Aggregate signals
                df = self._aggregate_bulk_deals(df, lookback_days)

            return df

        except Exception as e:
            logger.error(f"Error loading NSE bulk deals: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def _aggregate_bulk_deals(self, df: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
        """Aggregate bulk deal signals per ticker."""
        if 'Ticker' not in df.columns or 'Quantity' not in df.columns:
            return df
        
        # Compute net buy pressure. The old code multiplied by
        # df.get('BuySellFlag', 1): that column NEVER exists (the deal side lives
        # in DealType/deal_type as 'BUY'/'SELL'), so DataFrame.get returned the
        # scalar default 1 and every SELL was counted as a BUY — net_buy_pressure
        # collapsed to gross volume and "institutional_accumulation" was just
        # top-quartile turnover. Derive the ±1 sign from the actual deal side.
        side_col = next((c for c in ('DealType', 'deal_type', 'BuySellFlag') if c in df.columns), None)
        if side_col is not None:
            side = df[side_col].astype(str).str.upper().str.strip()
            sign = np.where(side.str.startswith('S'), -1.0, 1.0)  # SELL -> -1, else BUY
        else:
            logger.warning("bulk deals missing deal-side column; net_buy_pressure unsigned")
            sign = 1.0
        df['net_quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0.0) * sign
        
        # Aggregate over lookback period
        aggregated = df.groupby('Ticker').agg({
            'net_quantity': 'sum',
            'Quantity': 'sum',
            'TradeDate': 'max'
        }).reset_index()
        
        aggregated = aggregated.rename(columns={
            'net_quantity': 'net_buy_pressure',
            'Quantity': 'total_volume',
            'TradeDate': 'latest_trade_date'
        })
        
        # Institutional accumulation flag (top quartile)
        if len(aggregated) > 0:
            threshold = aggregated['net_buy_pressure'].quantile(0.75)
            aggregated['institutional_accumulation'] = aggregated['net_buy_pressure'] > threshold
        
        return aggregated
    
    def load_promoter_pledges(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load promoter pledge data with risk indicators.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            
        Returns:
            DataFrame with (Ticker, QuarterEnd) as index
        """
        try:
            pledge_path = Path(
                self.paths_config.get(
                    'promoter_pledges_processed',
                    self.paths_config.get('promoter_pledges', 'data/processed/alternative/promoter_pledge_all.csv'),
                )
            )
            
            if not pledge_path.exists():
                pledge_path = Path('data/raw/exchanges/bse/alternative/promoter_pledge')
                if not pledge_path.exists():
                    logger.warning("Promoter pledge data not found")
                    return pd.DataFrame()
            
            # Handle directory of CSVs
            if pledge_path.is_dir():
                csv_files = list(pledge_path.glob('*_pledge.csv'))
                if not csv_files:
                    logger.warning("No promoter pledge CSV files found")
                    return pd.DataFrame()
                
                dfs = []
                for csv_file in csv_files:
                    try:
                        df_temp = pd.read_csv(csv_file)
                        dfs.append(df_temp)
                    except Exception as e:
                        logger.warning(f"Error reading {csv_file}: {e}")
                
                if not dfs:
                    return pd.DataFrame()
                
                df = pd.concat(dfs, ignore_index=True)
            else:
                # Single file
                if pledge_path.suffix == '.csv':
                    df = pd.read_csv(pledge_path)
                else:
                    df = pd.read_parquet(pledge_path)
            
            # Standardize column names (actual data has: date, nse_ticker, pledge_pct)
            if 'nse_ticker' in df.columns:
                df = df.rename(columns={'nse_ticker': 'Ticker'})
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'QuarterEnd'})
            if 'pledge_pct' in df.columns:
                df = df.rename(columns={'pledge_pct': 'PledgePct'})
            
            # Convert date
            if 'QuarterEnd' in df.columns:
                df['QuarterEnd'] = pd.to_datetime(df['QuarterEnd'], errors='coerce')
                df = df.dropna(subset=['QuarterEnd'])
            
            # Filter by tickers
            if tickers and 'Ticker' in df.columns:
                # Normalize tickers
                normalized_tickers = []
                for ticker in tickers:
                    if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                        normalized_tickers.append(f"{ticker}.NS")
                    else:
                        normalized_tickers.append(ticker)
                df = df[df['Ticker'].isin(normalized_tickers)]
            
            # PIT enforcement (21-day lag, same as shareholding)
            if 'QuarterEnd' in df.columns:
                df['AvailabilityDate'] = df['QuarterEnd'] + timedelta(days=21)
                df = df[df['AvailabilityDate'] <= as_of_date].copy()
                self._validate_pit(df, 'AvailabilityDate', as_of_date)
                
                # Compute risk indicators
                df = self._compute_pledge_indicators(df)
                
                if 'Ticker' in df.columns:
                    df = df.set_index(['Ticker', 'QuarterEnd'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading promoter pledges: {e}")
            return pd.DataFrame()
    
    def _compute_pledge_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute pledge risk indicators."""
        if 'PledgePct' in df.columns and 'Ticker' in df.columns:
            df = df.sort_values(['Ticker', 'QuarterEnd'])
            
            # QoQ change in pledge
            df['pledge_change_qoq'] = df.groupby('Ticker')['PledgePct'].diff()
            
            # High pledge flag (>30%)
            high_pledge_threshold = self.config.get('high_pledge_threshold', 30.0)
            df['high_pledge_flag'] = df['PledgePct'] > high_pledge_threshold
            
            # Pledge increasing flag (2 consecutive quarters)
            df['pledge_increasing'] = (
                (df['pledge_change_qoq'] > 0) &
                (df.groupby('Ticker')['pledge_change_qoq'].shift(1) > 0)
            )
        
        return df
    
    def load_all_alternative(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load all alternative data sources.
        
        Handles individual loader failures gracefully.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            
        Returns:
            Dict keyed by source name with DataFrames as values
        """
        results = {}
        
        # GST
        try:
            results['gst'] = self.load_gst(as_of_date)
        except Exception as e:
            logger.warning(f"Failed to load GST data: {e}")
            results['gst'] = pd.DataFrame()
        
        # Power
        try:
            results['power'] = self.load_power_consumption(as_of_date)
        except Exception as e:
            logger.warning(f"Failed to load power data: {e}")
            results['power'] = pd.DataFrame()
        
        # Credit ratings
        try:
            results['credit_ratings'] = self.load_credit_ratings(as_of_date, tickers)
        except Exception as e:
            logger.warning(f"Failed to load credit ratings: {e}")
            results['credit_ratings'] = pd.DataFrame()
        
        # Bulk deals
        try:
            results['bulk_deals'] = self.load_bulk_deals(as_of_date, tickers)
        except Exception as e:
            logger.warning(f"Failed to load bulk deals: {e}")
            results['bulk_deals'] = pd.DataFrame()
        
        # Promoter pledges
        try:
            results['promoter_pledges'] = self.load_promoter_pledges(as_of_date, tickers)
        except Exception as e:
            logger.warning(f"Failed to load promoter pledges: {e}")
            results['promoter_pledges'] = pd.DataFrame()
        
        # Log summary
        loaded = sum(1 for df in results.values() if not df.empty)
        logger.info(f"Loaded {loaded}/5 alternative data sources")
        
        return results
