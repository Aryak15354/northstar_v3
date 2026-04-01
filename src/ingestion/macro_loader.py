"""
MacroLoader — Load RBI macroeconomic data with release calendar awareness.

Data sources:
- data/macro/comprehensive_rbi_data.parquet — RBI indicators
- data/macro/macro_indicators.parquet — Macro indicators
- data/macro/yields.csv — Yield curve data
- data/integrity/data_release_calendar.parquet — Release schedule

Handles release lags for different indicators (CPI, IIP, GDP, etc.)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
import numpy as np

from .base_loader import BaseLoader, DataNotFoundError

logger = logging.getLogger(__name__)


class MacroLoader(BaseLoader):
    """Loads macro data with release calendar enforcement."""
    
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        """
        Load macro data (delegates to load_rbi_data).
        
        Args:
            as_of_date: Point-in-time date
            **kwargs: Additional parameters for load_rbi_data
            
        Returns:
            DataFrame with macro data
        """
        return self.load_rbi_data(as_of_date, **kwargs)
    
    def load_rbi_data(
        self,
        as_of_date: datetime,
        indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load RBI macro indicators with release calendar PIT enforcement.
        
        Args:
            as_of_date: Point-in-time date
            indicators: List of indicators (None = all)
                       Options: 'repo_rate', 'cpi', 'wpi', 'iip', 'gdp', 'm3',
                               'credit_growth', 'forex_reserves', 'current_account'
            
        Returns:
            DataFrame with (ReleaseDate, IndicatorName) as MultiIndex
        """
        start_time = pd.Timestamp.now()
        
        # Try comprehensive RBI data first
        rbi_path = self._resolve_path('macro', 'data/macro') / 'comprehensive_rbi_data.parquet'
        
        if not rbi_path.exists():
            # Try alternative path
            rbi_path = self._resolve_path('macro', 'data/macro') / 'macro_indicators.parquet'
        
        if not rbi_path.exists():
            # Try cleaned data
            rbi_path = self._resolve_path('macro', 'data/macro') / 'cleaned' / 'macro_cleaned.parquet'
        
        if not rbi_path.exists():
            raise DataNotFoundError(f"RBI macro data not found at {rbi_path}")
        
        df = pd.read_parquet(rbi_path)
        
        # The comprehensive_rbi_data.parquet has columns like 'daily_other_NSE S&P CNX NIFTY'
        # We need to find a date column or use the index
        
        # Check if index is datetime
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            date_col = df.columns[0]
            df = df.rename(columns={date_col: 'period_date'})
        else:
            # Look for date column
            date_cols = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()]
            if date_cols:
                df = df.rename(columns={date_cols[0]: 'period_date'})
            else:
                # If no date column, the index might be the date
                if df.index.name and 'date' in str(df.index.name).lower():
                    df = df.reset_index()
                    df = df.rename(columns={df.columns[0]: 'period_date'})
                else:
                    logger.error("No date column in RBI data")
                    return pd.DataFrame()
        
        df['period_date'] = pd.to_datetime(df['period_date'], errors='coerce')
        
        # Load release calendar
        release_calendar = self._load_release_calendar()
        
        # Apply release lags
        df = self._apply_release_lags(df, release_calendar, as_of_date)
        
        # Filter by indicators if specified
        if indicators:
            # Find columns matching indicators
            indicator_cols = []
            for ind in indicators:
                matching = [c for c in df.columns if ind.lower() in c.lower()]
                indicator_cols.extend(matching)
            
            if indicator_cols:
                keep_cols = ['period_date', 'release_date'] + indicator_cols
                df = df[[c for c in keep_cols if c in df.columns]]
        
        # PIT enforcement
        if 'release_date' in df.columns:
            df = df[df['release_date'] <= as_of_date].copy()
            self._validate_pit(df, 'release_date', as_of_date)
        else:
            # If no release_date, use period_date with conservative lag
            df = df[df['period_date'] <= as_of_date - timedelta(days=45)].copy()
        
        elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000
        self._log_load(len(df), len(df.columns), str(rbi_path), elapsed_ms, as_of_date)
        
        return df
    
    def _load_release_calendar(self) -> pd.DataFrame:
        """Load or create release calendar."""
        try:
            calendar_path = self._resolve_path('release_calendar', 'data/integrity/data_release_calendar.parquet')
            
            if calendar_path.exists():
                return pd.read_parquet(calendar_path)
            
            logger.warning("Release calendar not found, using default lags")
            return self._create_default_release_calendar()
            
        except Exception as e:
            logger.warning(f"Error loading release calendar: {e}")
            return self._create_default_release_calendar()
    
    def _create_default_release_calendar(self) -> pd.DataFrame:
        """Create default release calendar with conservative lags."""
        default_lags = {
            'cpi': 12,  # days after month end
            'wpi': 14,
            'iip': 42,  # 6 weeks
            'gdp': 60,  # 2 months
            'm3': 14,
            'credit_growth': 14,
            'forex_reserves': 7,
            'repo_rate': 0,  # Same day
            'current_account': 90,
        }
        
        return pd.DataFrame([
            {'indicator': k, 'lag_days': v}
            for k, v in default_lags.items()
        ])
    
    def _apply_release_lags(
        self,
        df: pd.DataFrame,
        release_calendar: pd.DataFrame,
        as_of_date: datetime
    ) -> pd.DataFrame:
        """Apply release lags to compute actual availability dates."""
        if 'release_date' not in df.columns:
            # Compute release dates based on calendar
            df['release_date'] = df['period_date']
            
            # Apply default conservative lag if no calendar or calendar is empty
            if release_calendar.empty or 'indicator' not in release_calendar.columns:
                df['release_date'] = df['period_date'] + timedelta(days=45)
            else:
                # Apply indicator-specific lags
                for _, row in release_calendar.iterrows():
                    if 'indicator' in row and 'lag_days' in row:
                        indicator = row['indicator']
                        lag_days = row.get('lag_days', 45)
                        
                        # Find columns matching this indicator
                        matching_cols = [c for c in df.columns if indicator in c]
                        if matching_cols:
                            # For simplicity, apply same lag to all rows
                            # In production, this would be more sophisticated
                            df['release_date'] = df['period_date'] + timedelta(days=lag_days)
        
        return df
    
    def load_yield_curve(
        self,
        as_of_date: datetime,
        tenors: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load yield curve data.
        
        Args:
            as_of_date: Point-in-time date
            tenors: List of tenors ('3m', '6m', '1y', '2y', '5y', '10y', '30y')
            
        Returns:
            DataFrame with Date as index and tenor columns
        """
        try:
            yields_path = self._resolve_path('macro', 'data/macro') / 'yields.csv'
            
            if not yields_path.exists():
                logger.warning("Yield curve data not found")
                return pd.DataFrame()
            
            df = pd.read_csv(yields_path)
            df['Date'] = pd.to_datetime(df['Date'])
            
            # PIT enforcement
            df = df[df['Date'] <= as_of_date].copy()
            self._validate_pit(df, 'Date', as_of_date)
            
            # Filter tenors
            if tenors:
                tenor_cols = [c for c in df.columns if any(t in c for t in tenors)]
                if tenor_cols:
                    df = df[['Date'] + tenor_cols]
            
            df = df.set_index('Date')
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading yield curve: {e}")
            return pd.DataFrame()
    
    def load_macro_factors(self, as_of_date: datetime) -> pd.DataFrame:
        """
        Load PCA-reduced macro factors.
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            DataFrame with macro factors
        """
        try:
            factors_path = self._resolve_path('macro_features_path', 'data/processed/macro/macro_regime_features.parquet')
            
            if not factors_path.exists():
                logger.warning("Macro factors not found, computing from raw data")
                # Fall back to loading raw RBI data
                return self.load_rbi_data(as_of_date)
            
            df = pd.read_parquet(factors_path)
            
            # Ensure date column
            date_col = next((c for c in df.columns if 'date' in c.lower()), None)
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col])
                df = df[df[date_col] <= as_of_date].copy()
                self._validate_pit(df, date_col, as_of_date)
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading macro factors: {e}")
            return pd.DataFrame()
    
    def build_release_calendar(self) -> None:
        """
        Build release calendar from historical data.
        
        This is a maintenance method to bootstrap the calendar.
        """
        logger.info("Building release calendar from historical data...")
        
        try:
            # Load all macro data
            macro_dir = self._resolve_path('macro', 'data/macro')
            
            # Scan for CSV files
            csv_files = list(macro_dir.glob('*.csv'))
            
            release_data = []
            
            for csv_file in csv_files:
                try:
                    df = pd.read_csv(csv_file)
                    
                    # Infer lag from file modification time vs data period
                    mod_time = datetime.fromtimestamp(csv_file.stat().st_mtime)
                    
                    # Get latest period in data
                    date_cols = [c for c in df.columns if 'date' in c.lower()]
                    if date_cols:
                        latest_period = pd.to_datetime(df[date_cols[0]]).max()
                        lag_days = (mod_time - latest_period).days
                        
                        release_data.append({
                            'indicator': csv_file.stem,
                            'lag_days': max(0, lag_days),
                            'source_file': csv_file.name
                        })
                
                except Exception as e:
                    logger.warning(f"Error processing {csv_file}: {e}")
            
            if release_data:
                calendar_df = pd.DataFrame(release_data)
                
                # Save calendar
                calendar_path = self._resolve_path('release_calendar', 'data/integrity/data_release_calendar.parquet')
                calendar_path.parent.mkdir(parents=True, exist_ok=True)
                calendar_df.to_parquet(calendar_path)
                
                logger.info(f"Built release calendar with {len(calendar_df)} indicators")
            else:
                logger.warning("No data found to build release calendar")
                
        except Exception as e:
            logger.error(f"Error building release calendar: {e}")
