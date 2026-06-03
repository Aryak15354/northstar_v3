#!/usr/bin/env python3
"""
🔧 MACRO PREPROCESSOR - MIE COMPONENT 2
Stationarize, standardize, and construct lagged variables

Statistical Controls:
- Stationarity testing (ADF test)
- Differencing for non-stationary series
- Standardization (z-score)
- Lag construction (0 to 52 weeks)
- Outlier handling (winsorization)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy import stats
import re
import warnings
warnings.filterwarnings('ignore')


class MacroPreprocessor:
    """
    Preprocessing engine for macro-equity transmission analysis
    
    Ensures statistical validity:
    - Stationarity (required for regression)
    - Standardization (comparable coefficients)
    - Lag structure (transmission delays)
    - Outlier control (robust estimation)
    """
    
    def __init__(
        self,
        lags: List[int] = [0, 1, 2, 4, 8, 12, 26],  # weeks
        winsorize_pct: float = 0.01,  # 1% winsorization
        min_obs_pct: float = 0.5  # Require 50% non-null
    ):
        self.lags = sorted(lags)
        self.winsorize_pct = winsorize_pct
        self.min_obs_pct = min_obs_pct
        
        # Store transformation metadata
        self.transformation_log = {}
        
        print(f"🔧 Macro Preprocessor initialized")
        print(f"   Lags: {self.lags}")
        print(f"   Winsorization: {self.winsorize_pct*100}%")
    
    def check_stationarity(self, series: pd.Series, name: str = "") -> Dict:
        """
        Test for stationarity using Augmented Dickey-Fuller test
        
        Args:
            series: Time series to test
            name: Variable name for logging
        
        Returns:
            Dict with test results
        """
        # Remove NaN
        clean_series = series.dropna()
        
        if len(clean_series) < 30:
            return {
                'is_stationary': False,
                'reason': 'insufficient_data',
                'p_value': np.nan
            }

        try:
            from statsmodels.tsa.stattools import adfuller  # type: ignore
        except Exception:
            # Fallback heuristic when statsmodels is unavailable.
            # Compare level/variance drift between first and second half.
            arr = clean_series.astype(float).values
            half = len(arr) // 2
            if half < 10:
                return {
                    'is_stationary': False,
                    'reason': 'insufficient_data',
                    'p_value': np.nan
                }
            a = arr[:half]
            b = arr[half:]
            std_all = float(np.nanstd(arr) + 1e-12)
            mean_shift = abs(float(np.nanmean(a) - np.nanmean(b))) / std_all
            var_a = float(np.nanvar(a) + 1e-12)
            var_b = float(np.nanvar(b) + 1e-12)
            var_ratio = max(var_a, var_b) / min(var_a, var_b)
            is_stationary = bool(mean_shift < 0.35 and var_ratio < 2.5)
            return {
                'is_stationary': is_stationary,
                'reason': 'heuristic_no_statsmodels',
                'p_value': np.nan
            }

        try:
            result = adfuller(clean_series, autolag='AIC')
            p_value = result[1]
            is_stationary = p_value < 0.05  # 5% significance
            
            return {
                'is_stationary': is_stationary,
                'p_value': p_value,
                'test_statistic': result[0],
                'critical_values': result[4]
            }
        except Exception as e:
            return {
                'is_stationary': False,
                'reason': f'test_failed: {str(e)}',
                'p_value': np.nan
            }

    @staticmethod
    def _infer_unit_family(column_name: str) -> str:
        name = str(column_name).lower()
        compact = re.sub(r"\s+", " ", name).strip()
        if any(tok in compact for tok in ["%", "percent", "rate", "yield", "inflation", "repo", "crr", "slr"]):
            return "rate_or_ratio"
        if any(tok in compact for tok in ["usd", "us $", "dollar", "inr", "rupee", "crore", "lakh", "million", "billion"]):
            return "money"
        if any(tok in compact for tok in ["index", "cpi", "wpi", "exchange rate", "price index"]):
            return "index_or_level"
        if any(tok in compact for tok in ["credit", "deposit", "debt", "reserves", "trade", "exports", "imports", "balance", "m3"]):
            return "flow_or_stock"
        return "unknown"
    
    def make_stationary(
        self,
        df: pd.DataFrame,
        method: str = 'auto'
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Transform variables to achieve stationarity
        
        Args:
            df: DataFrame with time series
            method: 'auto', 'difference', 'log_difference', 'none'
        
        Returns:
            Tuple of (stationary_df, transformation_log)
        """
        print(f"\n📊 Making variables stationary...")
        
        stationary_df = pd.DataFrame(index=df.index)
        transformation_log = {}
        
        for col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            unit_family = self._infer_unit_family(col)
            prefer_log = bool(unit_family in {"money", "index_or_level", "flow_or_stock"} and (series.dropna() > 0).all())
            
            # Check if already stationary
            stationarity_test = self.check_stationarity(series, col)
            
            if stationarity_test['is_stationary']:
                # Already stationary
                stationary_df[col] = series
                transformation_log[col] = {
                    'transformation': 'none',
                    'p_value': stationarity_test['p_value'],
                    'unit_family': unit_family,
                }
            else:
                diff_series = series.diff()
                diff_test = self.check_stationarity(diff_series, f"{col}_diff")

                log_diff_series = None
                log_diff_test = {'is_stationary': False, 'p_value': np.nan}
                if prefer_log:
                    log_diff_series = np.log(series).diff()
                    log_diff_test = self.check_stationarity(log_diff_series, f"{col}_logdiff")

                if prefer_log and bool(log_diff_test.get('is_stationary')):
                    stationary_df[col] = log_diff_series
                    transformation_log[col] = {
                        'transformation': 'log_difference',
                        'p_value': log_diff_test.get('p_value', np.nan),
                        'unit_family': unit_family,
                    }
                elif bool(diff_test.get('is_stationary')):
                    stationary_df[col] = diff_series
                    transformation_log[col] = {
                        'transformation': 'difference',
                        'p_value': diff_test.get('p_value', np.nan),
                        'unit_family': unit_family,
                    }
                elif prefer_log and log_diff_series is not None:
                    stationary_df[col] = log_diff_series
                    transformation_log[col] = {
                        'transformation': 'log_difference_forced',
                        'p_value': log_diff_test.get('p_value', np.nan),
                        'unit_family': unit_family,
                    }
                else:
                    stationary_df[col] = diff_series
                    transformation_log[col] = {
                        'transformation': 'difference_forced',
                        'p_value': diff_test.get('p_value', np.nan),
                        'unit_family': unit_family,
                    }
        
        # Count transformations
        transform_counts = {}
        for info in transformation_log.values():
            t = info['transformation']
            transform_counts[t] = transform_counts.get(t, 0) + 1
        
        print(f"   ✓ Transformation summary:")
        for transform, count in transform_counts.items():
            print(f"      {transform}: {count} variables")
        
        self.transformation_log = transformation_log
        return stationary_df, transformation_log
    
    def standardize(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        Standardize variables to z-scores (mean=0, std=1)
        
        Args:
            df: DataFrame with time series
        
        Returns:
            Tuple of (standardized_df, standardization_params)
        """
        print(f"\n📏 Standardizing variables...")
        
        standardized_df = pd.DataFrame(index=df.index)
        standardization_params = {}
        
        for col in df.columns:
            series = df[col].dropna()
            
            if len(series) < 10:
                # Skip if insufficient data
                standardized_df[col] = np.nan
                standardization_params[col] = {
                    'mean': np.nan,
                    'std': np.nan,
                    'skipped': True
                }
                continue
            
            mean = series.mean()
            std = series.std()
            
            if std == 0 or np.isnan(std):
                # Constant series
                standardized_df[col] = 0
                standardization_params[col] = {
                    'mean': mean,
                    'std': 0,
                    'constant': True
                }
            else:
                # Z-score standardization
                standardized_df[col] = (df[col] - mean) / std
                standardization_params[col] = {
                    'mean': mean,
                    'std': std
                }
        
        print(f"   ✓ Standardized {len(df.columns)} variables")
        
        return standardized_df, standardization_params
    
    def winsorize(self, df: pd.DataFrame, pct: Optional[float] = None) -> pd.DataFrame:
        """
        Winsorize outliers to reduce influence of extreme values
        
        Args:
            df: DataFrame with time series
            pct: Winsorization percentage (default: self.winsorize_pct)
        
        Returns:
            Winsorized DataFrame
        """
        if pct is None:
            pct = self.winsorize_pct
        
        print(f"\n✂️ Winsorizing outliers at {pct*100}%...")
        
        winsorized_df = df.copy()
        
        for col in df.columns:
            series = df[col].dropna()
            
            if len(series) < 10:
                continue
            
            # Compute percentiles
            lower = series.quantile(pct)
            upper = series.quantile(1 - pct)
            
            # Winsorize
            winsorized_df[col] = df[col].clip(lower=lower, upper=upper)
        
        print(f"   ✓ Winsorized {len(df.columns)} variables")
        
        return winsorized_df
    
    def construct_lags(
        self,
        df: pd.DataFrame,
        lags: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """
        Construct lagged variables for transmission analysis
        
        Args:
            df: DataFrame with time series
            lags: List of lag periods (default: self.lags)
        
        Returns:
            DataFrame with original + lagged variables
        """
        if lags is None:
            lags = self.lags
        
        print(f"\n⏱️ Constructing lagged variables...")
        print(f"   Lags: {lags}")
        
        lagged_df = pd.DataFrame(index=df.index)
        
        for col in df.columns:
            # Add contemporaneous (lag 0)
            if 0 in lags:
                lagged_df[f"{col}_lag0"] = df[col]
            
            # Add lagged versions
            for lag in lags:
                if lag > 0:
                    lagged_df[f"{col}_lag{lag}"] = df[col].shift(lag)
        
        print(f"   ✓ Created {len(lagged_df.columns)} lagged variables")
        print(f"      ({len(df.columns)} original × {len(lags)} lags)")
        
        return lagged_df
    
    def filter_by_coverage(
        self,
        df: pd.DataFrame,
        min_pct: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Filter out variables with insufficient data coverage
        
        Args:
            df: DataFrame with time series
            min_pct: Minimum non-null percentage (default: self.min_obs_pct)
        
        Returns:
            Filtered DataFrame
        """
        if min_pct is None:
            min_pct = self.min_obs_pct
        
        print(f"\n🔍 Filtering variables by coverage (min {min_pct*100}%)...")
        
        coverage = df.notna().sum() / len(df)
        valid_cols = coverage[coverage >= min_pct].index.tolist()
        
        filtered_df = df[valid_cols]
        
        print(f"   ✓ Kept {len(valid_cols)} / {len(df.columns)} variables")
        print(f"   ✗ Dropped {len(df.columns) - len(valid_cols)} variables")
        
        return filtered_df
    
    def preprocess_macro(
        self,
        macro_df: pd.DataFrame,
        make_stationary: bool = True,
        standardize: bool = True,
        winsorize: bool = True,
        construct_lags: bool = True
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Full preprocessing pipeline for macro variables
        
        Args:
            macro_df: Raw macro DataFrame
            make_stationary: Apply stationarity transformation
            standardize: Apply z-score standardization
            winsorize: Apply outlier winsorization
            construct_lags: Construct lagged variables
        
        Returns:
            Tuple of (processed_df, metadata)
        """
        print("=" * 80)
        print("🔧 MACRO PREPROCESSING PIPELINE")
        print("=" * 80)
        
        processed_df = macro_df.copy()
        metadata = {}
        
        # Step 1: Filter by coverage
        processed_df = self.filter_by_coverage(processed_df)
        
        # Step 2: Make stationary
        if make_stationary:
            processed_df, transform_log = self.make_stationary(processed_df)
            metadata['transformations'] = transform_log
        
        # Step 3: Winsorize outliers
        if winsorize:
            processed_df = self.winsorize(processed_df)
        
        # Step 4: Standardize
        if standardize:
            processed_df, std_params = self.standardize(processed_df)
            metadata['standardization'] = std_params
        
        # Step 5: Construct lags
        if construct_lags:
            processed_df = self.construct_lags(processed_df)
        
        # Final cleanup
        processed_df = processed_df.dropna(how='all', axis=1)  # Drop all-NaN columns
        
        print("\n" + "=" * 80)
        print("✅ PREPROCESSING COMPLETE")
        print(f"   Final variables: {len(processed_df.columns)}")
        print(f"   Final observations: {len(processed_df)}")
        print("=" * 80)
        
        return processed_df, metadata
    
    def preprocess_returns(
        self,
        returns_df: pd.DataFrame,
        winsorize: bool = True
    ) -> pd.DataFrame:
        """
        Preprocess company returns (simpler than macro)
        
        Args:
            returns_df: Raw returns DataFrame
            winsorize: Apply outlier winsorization
        
        Returns:
            Processed returns DataFrame
        """
        print("\n📈 Preprocessing company returns...")
        
        processed_df = returns_df.copy()
        
        # Winsorize if requested
        if winsorize:
            processed_df = self.winsorize(processed_df, pct=0.01)
        
        # Filter by coverage
        processed_df = self.filter_by_coverage(processed_df, min_pct=0.3)
        
        print(f"   ✓ Processed {len(processed_df.columns)} companies")
        
        return processed_df
