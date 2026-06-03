"""
BaseFactor — Abstract base class for all Northstar V3 factor signals.

Design principles:
1. PIT-SAFE: Every factor computation is anchored to an as_of_date.
   No data after as_of_date is ever used. For fundamental factors,
   an additional reporting_lag_days is enforced.
2. UNIVERSE-CONSISTENT: Factors are always computed on the full
   provided universe, with explicit handling for missing tickers.
   A ticker missing from the output is treated as NaN, not excluded.
3. NORMALIZED: Raw factor values are transformed to z-scores
   cross-sectionally within the provided universe. Z-score is winsorized
   at ±3 before normalization to prevent outliers from dominating.
4. CACHED: Computed factor scores are cached in data/factors/ so that
   historical dataset construction does not recompute the same date twice.
5. AUDITABLE: Every factor computation writes a small metadata record
   to data/factors/factor_computation_log.jsonl for audit purposes.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
import json
import logging

logger = logging.getLogger(__name__)


class BaseFactor(ABC):
    """Abstract base class for all factor signals."""
    
    FACTOR_NAME: str = ""          # Override in each subclass
    FACTOR_FAMILY: str = ""        # "MOMENTUM", "VALUE", "QUALITY", "LIQUIDITY", "RISK"
    LOOKAHEAD_SAFE: bool = True    # Set False during development, True when PIT-verified
    
    def __init__(self, registry, config: dict):
        """
        Parameters
        ----------
        registry : IngestionRegistry
            The unified data access layer from Gap 1.
        config : dict
            Full system config. Factor reads from config['factors'][FACTOR_NAME].
        """
        self._registry = registry
        self._config = config
        self._factor_config = config.get('factors', {}).get(self.FACTOR_NAME, {})
        # Keep the single-date factor cache separate from the historical FactorStore
        # parquet files, which use a different schema under data/factors/.
        self._cache_path = Path(f"data/factors/cache/{self.FACTOR_NAME}_scores.parquet")
        self._audit_log_path = Path("data/factors/factor_computation_log.jsonl")
        
        # Ensure directories exist
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    def _compute_raw(
        self,
        as_of_date: datetime,
        tickers: list
    ) -> pd.Series:
        """
        Compute the raw (unnormalized) factor value for each ticker.
        
        Parameters
        ----------
        as_of_date : datetime
            The point-in-time date. No data after this date may be used.
        tickers : list
            The universe of tickers to compute for.
        
        Returns
        -------
        pd.Series
            Index: ticker symbols
            Values: raw factor values (unnormalized)
        """
        pass
    
    def compute(
        self,
        as_of_date: datetime,
        tickers: list,
        use_cache: bool = True,
        winsorize_std: float = 3.0
    ) -> pd.DataFrame:
        """
        Compute the normalized factor scores for the given universe and date.
        
        Returns a DataFrame with columns:
        - {FACTOR_NAME}_raw       : raw factor value before normalization
        - {FACTOR_NAME}_zscore    : cross-sectional z-score (winsorized)
        - {FACTOR_NAME}_rank      : cross-sectional percentile rank (0 to 1)
        - {FACTOR_NAME}_available : bool, True if data was available
        
        The z-score and rank columns are what FeatureFactory should use.
        """
        # Check cache first
        if use_cache:
            cached = self._load_from_cache(as_of_date, tickers)
            if cached is not None:
                return cached
        
        # Compute raw values
        raw_series = self._compute_raw(as_of_date, tickers)
        
        # Ensure full universe coverage (fill missing with NaN)
        raw_series = raw_series.reindex(tickers)
        
        # Winsorize at ±winsorize_std standard deviations
        non_null = raw_series.dropna()
        if len(non_null) >= 10:
            mean = non_null.mean()
            std = non_null.std()
            raw_series = raw_series.clip(
                lower=mean - winsorize_std * std,
                upper=mean + winsorize_std * std
            )
        
        # Cross-sectional z-score
        non_null_winsorized = raw_series.dropna()
        if len(non_null_winsorized) >= 10:
            zscore = (raw_series - non_null_winsorized.mean()) / (non_null_winsorized.std() + 1e-9)
        else:
            zscore = pd.Series(np.nan, index=tickers)
        
        # Cross-sectional percentile rank
        rank = raw_series.rank(pct=True)
        
        # Availability flag
        available = raw_series.notna()
        
        # Assemble result DataFrame
        result = pd.DataFrame({
            f'{self.FACTOR_NAME}_raw': raw_series,
            f'{self.FACTOR_NAME}_zscore': zscore,
            f'{self.FACTOR_NAME}_rank': rank,
            f'{self.FACTOR_NAME}_available': available,
        }, index=tickers)
        
        # Write to cache
        self._write_to_cache(as_of_date, result)
        
        # Write audit log
        self._write_audit_log(as_of_date, result)
        
        return result

    def get_output_columns(self, include_meta: bool = True) -> list[str]:
        columns = [
            f'{self.FACTOR_NAME}_raw',
            f'{self.FACTOR_NAME}_zscore',
            f'{self.FACTOR_NAME}_rank',
        ]
        if include_meta:
            columns.append(f'{self.FACTOR_NAME}_available')
        return columns

    def get_feature_names(self, include_raw: bool = False) -> list[str]:
        names = []
        if include_raw:
            names.append(f'{self.FACTOR_NAME}_raw')
        names.extend([f'{self.FACTOR_NAME}_zscore', f'{self.FACTOR_NAME}_rank'])
        return names

    def get_primary_zscore_column(self) -> str:
        return f'{self.FACTOR_NAME}_zscore'
    
    def _load_from_cache(self, as_of_date: datetime, tickers: list) -> Optional[pd.DataFrame]:
        """Load cached factor scores for this date if available."""
        if not self._cache_path.exists():
            return None
        
        try:
            df = pd.read_parquet(self._cache_path)
            
            # Check if we have data for this date
            if 'date' not in df.columns:
                return None
            
            date_mask = pd.to_datetime(df['date']).dt.date == as_of_date.date()
            date_data = df[date_mask]
            
            if date_data.empty:
                return None
            
            # Check if we have all tickers
            ticker_set = set(tickers)
            available_tickers = set(date_data['ticker'].tolist())
            
            if not ticker_set.issubset(available_tickers):
                # Missing some tickers - return None to force recomputation
                return None
            
            # Pivot to wide format
            result = date_data.pivot(index='ticker', columns='metric', values='value')
            result = result.reindex(tickers)
            
            logger.debug(f"Loaded cached {self.FACTOR_NAME} for {as_of_date.date()}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to load cache for {self.FACTOR_NAME}: {e}")
            return None
    
    def _write_to_cache(self, as_of_date: datetime, result: pd.DataFrame) -> None:
        """Append computed scores to the factor's parquet cache file."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to long format for efficient storage
            long_df = result.reset_index()
            long_df['date'] = as_of_date.date()
            long_df = long_df.melt(
                id_vars=['index', 'date'],
                var_name='metric',
                value_name='value'
            )
            long_df = long_df.rename(columns={'index': 'ticker'})
            
            # Load existing cache
            if self._cache_path.exists():
                existing = pd.read_parquet(self._cache_path)
                
                # Remove old data for this date if present
                date_mask = ~(pd.to_datetime(existing['date']).dt.date == as_of_date.date())
                existing = existing[date_mask]
                
                # Append new data
                combined = pd.concat([existing, long_df], ignore_index=True)
            else:
                combined = long_df
            
            # Atomic write
            temp_path = self._cache_path.with_name(f"{self._cache_path.stem}.tmp.parquet")
            combined.to_parquet(temp_path, index=False)
            temp_path.rename(self._cache_path)
            
            logger.debug(f"Cached {self.FACTOR_NAME} for {as_of_date.date()}")
            
        except Exception as e:
            logger.error(f"Failed to write cache for {self.FACTOR_NAME}: {e}")
    
    def _write_audit_log(self, as_of_date: datetime, result: pd.DataFrame) -> None:
        """Append a metadata record to factor_computation_log.jsonl."""
        try:
            available = result[f'{self.FACTOR_NAME}_available'].sum()
            raw_col = result[f'{self.FACTOR_NAME}_raw']
            zscore_col = result[f'{self.FACTOR_NAME}_zscore']
            
            record = {
                'factor_name': self.FACTOR_NAME,
                'as_of_date': as_of_date.isoformat(),
                'universe_size': len(result),
                'tickers_with_data': int(available),
                'coverage_pct': float(available) / len(result) if len(result) > 0 else 0.0,
                'raw_mean': float(raw_col.mean()) if raw_col.notna().any() else None,
                'raw_std': float(raw_col.std()) if raw_col.notna().any() else None,
                'zscore_mean': float(zscore_col.mean()) if zscore_col.notna().any() else None,
                'zscore_std': float(zscore_col.std()) if zscore_col.notna().any() else None,
                'computed_at': datetime.now().isoformat()
            }
            
            with open(self._audit_log_path, 'a') as f:
                f.write(json.dumps(record) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to write audit log for {self.FACTOR_NAME}: {e}")
    
    def get_coverage(self, as_of_date: datetime, tickers: list) -> dict:
        """Returns coverage diagnostics for the given date and universe."""
        result = self.compute(as_of_date, tickers, use_cache=True)
        available = result[f'{self.FACTOR_NAME}_available'].sum()
        return {
            'factor_name': self.FACTOR_NAME,
            'as_of_date': as_of_date,
            'universe_size': len(tickers),
            'tickers_with_data': int(available),
            'coverage_pct': float(available) / len(tickers) if tickers else 0.0,
            'minimum_viable_coverage': self._factor_config.get('min_coverage_pct', 0.60)
        }

    def run_pit_leakage_test(
        self,
        tickers: list,
        test_dates: list,
        forward_returns: pd.DataFrame,
        correct_lag_days: int,
    ) -> Dict[str, Any]:
        """
        Compare PIT-correct scores against intentionally forward-shifted scores.

        A materially stronger no-lag IC is a strong indicator of leakage.
        """
        from scipy.stats import spearmanr

        lag_ics = []
        no_lag_ics = []
        zscore_col = self.get_primary_zscore_column()

        for test_date in test_dates:
            try:
                scores_with_lag = self.compute(test_date, tickers, use_cache=False)
            except Exception as exc:
                logger.warning("PIT lag test failed for %s on %s: %s", self.FACTOR_NAME, test_date, exc)
                continue

            try:
                lag_keys = [
                    key
                    for key in ('reporting_lag_days', 'announcement_safety_lag_days', 'safety_lag_days')
                    if key in self._factor_config
                ]
                if lag_keys and int(max(0, correct_lag_days)) > 0:
                    original_values = {key: self._factor_config.get(key) for key in lag_keys}
                    for key in lag_keys:
                        self._factor_config[key] = 0
                    try:
                        scores_no_lag = self.compute(test_date, tickers, use_cache=False)
                    finally:
                        for key, value in original_values.items():
                            self._factor_config[key] = value
                else:
                    no_lag_date = pd.Timestamp(test_date) + timedelta(days=int(max(0, correct_lag_days)))
                    scores_no_lag = self.compute(no_lag_date.to_pydatetime(), tickers, use_cache=False)
            except Exception as exc:
                logger.warning("PIT no-lag simulation failed for %s on %s: %s", self.FACTOR_NAME, test_date, exc)
                continue

            try:
                fwd_slice = forward_returns.loc[pd.Timestamp(test_date)]
            except Exception:
                continue

            if isinstance(fwd_slice, pd.Series) and 'fwd_5d_return' in fwd_slice.index:
                fwd = fwd_slice['fwd_5d_return']
            elif isinstance(fwd_slice, pd.DataFrame) and 'fwd_5d_return' in fwd_slice.columns:
                fwd = fwd_slice['fwd_5d_return']
            else:
                continue

            aligned_lag = scores_with_lag[zscore_col].reindex(fwd.index).dropna()
            aligned_no_lag = scores_no_lag[zscore_col].reindex(fwd.index).dropna()

            if len(aligned_lag) >= 10:
                lag_y = pd.to_numeric(fwd.reindex(aligned_lag.index), errors='coerce')
                mask = lag_y.notna()
                if int(mask.sum()) >= 10:
                    ic, _ = spearmanr(aligned_lag[mask], lag_y[mask])
                    if np.isfinite(ic):
                        lag_ics.append(float(ic))

            if len(aligned_no_lag) >= 10:
                no_lag_y = pd.to_numeric(fwd.reindex(aligned_no_lag.index), errors='coerce')
                mask = no_lag_y.notna()
                if int(mask.sum()) >= 10:
                    ic, _ = spearmanr(aligned_no_lag[mask], no_lag_y[mask])
                    if np.isfinite(ic):
                        no_lag_ics.append(float(ic))

        mean_lag = float(np.mean(lag_ics)) if lag_ics else 0.0
        mean_no_lag = float(np.mean(no_lag_ics)) if no_lag_ics else 0.0
        ratio = mean_no_lag / mean_lag if abs(mean_lag) > 1e-6 else 0.0
        return {
            'factor_name': self.FACTOR_NAME,
            'lag_ic': mean_lag,
            'no_lag_ic': mean_no_lag,
            'ratio': ratio,
            'leakage_detected': ratio > 1.20,
            'correct_lag_days': int(max(0, correct_lag_days)),
        }
