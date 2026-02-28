#!/usr/bin/env python3
"""
📊 MACRO DATA LOADER - MIE COMPONENT 1
Load and align RBI macro variables with company returns

Responsibilities:
- Load comprehensive RBI macro data
- Load company daily returns
- Align time series to common frequency
- Handle missing data intelligently
- Provide clean data matrices for analysis
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
import re
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

from src.utils.rbi_data_handler import rbi_handler


class MacroDataLoader:
    """
    Unified data loader for macro-equity transmission analysis
    
    Loads:
    - RBI macro variables (855 variables from comprehensive_rbi_data.parquet)
    - Company daily returns (from market data)
    - Sector mappings
    - Market factor (Nifty 50 for market beta control)
    """
    
    def __init__(
        self,
        macro_data_path: str = "data/macro/comprehensive_rbi_data.parquet",
        market_data_path: str = "data/market",
        sector_mapping_path: str = "config/sector_rules.json",
        target_frequency: str = 'W'  # Weekly by default
    ):
        self.macro_data_path = Path(macro_data_path)
        self.market_data_path = Path(market_data_path)
        self.sector_mapping_path = Path(sector_mapping_path)
        self.target_frequency = target_frequency
        
        # Data containers
        self.macro_df = None
        self.returns_df = None
        self.sector_map = None
        self.market_factor = None
        self.macro_unit_conversion_log: Dict[str, str] = {}
        self.macro_unit_profile: Dict[str, str] = {}
        
        print("🏛️ Macro Impact Engine - Data Loader initialized")

    @staticmethod
    def _ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if isinstance(out.index, pd.DatetimeIndex):
            out = out.sort_index()
            return out

        for c in ['date', 'Date', 'timestamp', 'Datetime', 'datetime']:
            if c in out.columns:
                out[c] = pd.to_datetime(out[c], errors='coerce')
                out = out.dropna(subset=[c]).set_index(c).sort_index()
                return out

        out.index = pd.to_datetime(out.index, errors='coerce')
        out = out[out.index.notna()].sort_index()
        return out

    @staticmethod
    def _wide_returns_from_prices_long(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        date_col = 'Date' if 'Date' in out.columns else ('date' if 'date' in out.columns else None)
        close_col = 'Close' if 'Close' in out.columns else ('close' if 'close' in out.columns else None)
        ticker_col = 'ticker' if 'ticker' in out.columns else ('Ticker' if 'Ticker' in out.columns else None)
        if date_col is None or close_col is None or ticker_col is None:
            return pd.DataFrame()

        out[date_col] = pd.to_datetime(out[date_col], errors='coerce')
        out[close_col] = pd.to_numeric(out[close_col], errors='coerce')
        out[ticker_col] = out[ticker_col].astype(str).str.strip()
        out = out.dropna(subset=[date_col, close_col, ticker_col])
        if out.empty:
            return pd.DataFrame()

        close_w = out.pivot_table(
            index=date_col, columns=ticker_col, values=close_col, aggfunc='last'
        ).sort_index()
        ret_w = close_w.pct_change(fill_method=None)
        return ret_w

    @staticmethod
    def _coerce_wide_returns_or_prices(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
        out = MacroDataLoader._ensure_datetime_index(df)
        if out.empty:
            return out

        numeric = out.select_dtypes(include=[np.number]).copy()
        if numeric.empty:
            return pd.DataFrame()

        # If source is explicitly prices, compute returns.
        if 'price' in source_name.lower():
            ret = numeric.pct_change(fill_method=None)
            return ret

        # Heuristic: identify likely returns-vs-prices.
        q99 = float(numeric.abs().stack().quantile(0.99)) if not numeric.empty else 0.0
        if q99 <= 1.5:
            return numeric
        return numeric.pct_change(fill_method=None)

    @staticmethod
    def _canonical_macro_name(name: str) -> str:
        text = str(name).strip()
        text = re.sub(r"^v\d+[_\-\s]+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def _dedupe_macro_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        groups: Dict[str, List[str]] = {}
        for col in df.columns:
            raw = str(col).strip()
            low = raw.lower()
            if (
                raw == ""
                or "unnamed_col_" in low
                or low.startswith("unnamed:")
            ):
                continue
            canonical = cls._canonical_macro_name(raw)
            if canonical == "":
                continue
            groups.setdefault(canonical, []).append(raw)

        if not groups:
            return pd.DataFrame(index=df.index)

        out = pd.DataFrame(index=df.index)
        for canonical, cols in groups.items():
            sub = df[cols].apply(pd.to_numeric, errors="coerce")
            if sub.empty:
                continue
            if sub.shape[1] == 1:
                out[canonical] = sub.iloc[:, 0]
                continue

            coverage = sub.notna().mean()
            variability = sub.std(skipna=True).replace(0, np.nan).rank(pct=True).fillna(0.0)
            quality = coverage * 0.7 + variability * 0.3
            best_col = quality.sort_values(ascending=False).index[0]
            merged = sub[best_col].copy()
            merged = merged.where(merged.notna(), sub.mean(axis=1, skipna=True))
            out[canonical] = merged

        out = out.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="all")
        return out

    @staticmethod
    def _normalize_percent_like_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """
        Normalize percent-like macro series to decimal units.

        Why:
        Some RBI fields are expressed in '%' points (e.g., 6.5) while others are
        ratios/decimals (e.g., 0.065). Converting only clear percent-like columns
        avoids mixed-unit distortions in downstream non-standardized steps.
        """
        if df is None or df.empty:
            return pd.DataFrame(), {}

        out = df.copy()
        conversion_log: Dict[str, str] = {}
        percent_tokens = (
            "%", "percent", "ratio", "rate", "yield", "inflation",
            "repo", "reverse repo", "call money", "crr", "slr",
        )
        bps_tokens = ("bps", "basis point", "basis points")

        for col in list(out.columns):
            name = str(col).lower()
            if not any(tok in name for tok in percent_tokens):
                continue
            s = pd.to_numeric(out[col], errors="coerce")
            clean = s.dropna()
            if clean.empty:
                continue

            q95 = float(clean.abs().quantile(0.95))
            q50 = float(clean.abs().quantile(0.50))

            # Convert only when values look like percentage points (e.g., 6.5, 42, 110).
            # Keep already-decimal series untouched.
            should_convert = (q95 > 1.5) and (q95 <= 200.0) and (q50 >= 0.2)
            if should_convert:
                out[col] = s / 100.0
                conversion_log[str(col)] = "percent_to_decimal"
                continue

            # Basis points (e.g., 150 = 1.50%) -> decimal
            if any(tok in name for tok in bps_tokens):
                q95_bps = float(clean.abs().quantile(0.95))
                if 0.5 <= q95_bps <= 20000.0:
                    out[col] = s / 10000.0
                    conversion_log[str(col)] = "bps_to_decimal"

        return out, conversion_log

    @staticmethod
    def _infer_unit_family(column_name: str) -> str:
        name = str(column_name).lower()
        if any(tok in name for tok in ["%", "percent", "rate", "yield", "inflation", "repo", "ratio", "crr", "slr"]):
            return "rate_or_ratio"
        if any(tok in name for tok in ["usd", "us $", "dollar", "inr", "rupee", "crore", "lakh", "million", "billion"]):
            return "money"
        if any(tok in name for tok in ["credit", "deposit", "debt", "reserves", "trade", "exports", "imports", "balance of payments", "m3"]):
            return "flow_or_stock"
        if any(tok in name for tok in ["index", "cpi", "wpi", "exchange rate", "price index"]):
            return "index_or_level"
        if any(tok in name for tok in ["count", "number", "volume"]):
            return "count_or_volume"
        return "unknown"

    @classmethod
    def _build_unit_profile(cls, columns: List[str]) -> Dict[str, str]:
        profile: Dict[str, str] = {}
        for col in columns:
            profile[str(col)] = cls._infer_unit_family(str(col))
        return profile
    
    def load_macro_data(self, variable_subset: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Load RBI macro data
        
        Args:
            variable_subset: Optional list of specific variables to load
                           If None, loads all available variables
        
        Returns:
            DataFrame with datetime index and macro variables as columns
        """
        print(f"\n📥 Loading RBI macro data from: {self.macro_data_path}")
        
        if not self.macro_data_path.exists():
            raise FileNotFoundError(f"Macro data not found: {self.macro_data_path}")
        
        # Load comprehensive RBI data
        macro_df = pd.read_parquet(self.macro_data_path)
        
        # Ensure datetime index
        if not isinstance(macro_df.index, pd.DatetimeIndex):
            if 'Period' in macro_df.columns:
                macro_df['Period'] = pd.to_datetime(macro_df['Period'])
                macro_df = macro_df.set_index('Period')
            elif 'Date' in macro_df.columns:
                macro_df['Date'] = pd.to_datetime(macro_df['Date'])
                macro_df = macro_df.set_index('Date')
        
        # Sort by date
        macro_df = macro_df.sort_index()
        macro_df = self._dedupe_macro_columns(macro_df)
        macro_df, conversion_log = self._normalize_percent_like_columns(macro_df)
        unit_profile = self._build_unit_profile([str(c) for c in macro_df.columns])
        macro_df = macro_df.replace([np.inf, -np.inf], np.nan).dropna(how='all')

        # Filter to subset if specified
        if variable_subset:
            available_vars = [v for v in variable_subset if v in macro_df.columns]
            if not available_vars:
                raise ValueError(f"None of the requested variables found in macro data")
            macro_df = macro_df[available_vars]
            print(f"   ✓ Loaded {len(available_vars)} macro variables")
        else:
            print(f"   ✓ Loaded {len(macro_df.columns)} macro variables")
        if conversion_log:
            print(f"   ✓ Unit-normalized {len(conversion_log)} percent-like macro series")
        if unit_profile:
            family_counts = Counter(unit_profile.values())
            parts = [f"{fam}={int(cnt)}" for fam, cnt in sorted(family_counts.items())]
            print(f"   ✓ Unit family profile: {', '.join(parts)}")
        
        print(f"   ✓ Date range: {macro_df.index.min()} to {macro_df.index.max()}")
        print(f"   ✓ Observations: {len(macro_df)}")
        
        self.macro_df = macro_df
        self.macro_unit_conversion_log = conversion_log
        self.macro_unit_profile = unit_profile
        return macro_df
    
    def load_company_returns(
        self,
        tickers: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load company daily returns
        
        Args:
            tickers: List of company tickers (e.g., ['SBIN.NS', 'RELIANCE.NS'])
                    If None, loads all available companies
            start_date: Start date for returns (YYYY-MM-DD)
            end_date: End date for returns (YYYY-MM-DD)
        
        Returns:
            DataFrame with datetime index and company returns as columns
        """
        print(f"\n📈 Loading company returns data")
        
        # Try multiple data sources
        returns_sources = [
            Path("data/processed/returns_daily.parquet"),
            Path("data/processed/prices.parquet"),
            self.market_data_path / "returns_daily.parquet",
            self.market_data_path / "prices_daily.parquet",
            self.market_data_path / "daily_prices.parquet",
        ]
        
        returns_df = None
        for source in returns_sources:
            if source.exists():
                print(f"   Loading from: {source}")
                raw = pd.read_parquet(source)

                # Long-format prices (Date, ticker, Close)
                if {'Date', 'ticker', 'Close'}.issubset(raw.columns) or {'date', 'ticker', 'close'}.issubset(raw.columns):
                    df = self._wide_returns_from_prices_long(raw)
                else:
                    df = self._coerce_wide_returns_or_prices(raw, source.name)

                df = self._ensure_datetime_index(df)
                df = df.replace([np.inf, -np.inf], np.nan).dropna(how='all')
                if df.empty:
                    continue
                returns_df = df
                break
        
        if returns_df is None:
            raise FileNotFoundError(f"No returns data found in {self.market_data_path}")
        
        # Filter by tickers if specified
        if tickers:
            available_tickers = [t for t in tickers if t in returns_df.columns]
            if not available_tickers:
                raise ValueError(f"None of the requested tickers found in returns data")
            returns_df = returns_df[available_tickers]
        
        # Filter by date range
        if start_date:
            returns_df = returns_df[returns_df.index >= pd.to_datetime(start_date)]
        if end_date:
            returns_df = returns_df[returns_df.index <= pd.to_datetime(end_date)]
        
        # Sort by date
        returns_df = returns_df.sort_index()

        print(f"   ✓ Loaded {len(returns_df.columns)} companies")
        print(f"   ✓ Date range: {returns_df.index.min()} to {returns_df.index.max()}")
        print(f"   ✓ Observations: {len(returns_df)}")
        
        self.returns_df = returns_df
        return returns_df
    
    def load_sector_mapping(self) -> Dict[str, str]:
        """
        Load sector mapping for companies
        
        Returns:
            Dictionary mapping ticker -> sector
        """
        print(f"\n🏭 Loading sector mappings")
        
        sector_map: Dict[str, str] = {}

        # Primary: config/sector_rules.json if it contains explicit ticker mappings.
        if self.sector_mapping_path.exists():
            try:
                with open(self.sector_mapping_path, 'r') as f:
                    sector_data = json.load(f)
                if isinstance(sector_data, dict) and 'sectors' in sector_data:
                    for sector, info in sector_data['sectors'].items():
                        tickers = (info or {}).get('tickers', []) if isinstance(info, dict) else []
                        for ticker in tickers:
                            t = str(ticker).strip()
                            if t:
                                sector_map[t] = str(sector)
            except Exception as e:
                print(f"   ⚠️ Could not parse {self.sector_mapping_path}: {e}")

        # Fallback: processed sector mapping artifact.
        if not sector_map:
            csv_path = Path("data/processed/sector_mapping.csv")
            if csv_path.exists():
                try:
                    sdf = pd.read_csv(csv_path)
                    tcol = 'ticker' if 'ticker' in sdf.columns else None
                    scol = 'sector' if 'sector' in sdf.columns else ('industry' if 'industry' in sdf.columns else None)
                    if tcol and scol:
                        sdf[tcol] = sdf[tcol].astype(str).str.strip()
                        sdf[scol] = sdf[scol].astype(str).str.strip()
                        sdf = sdf[(sdf[tcol] != "") & (sdf[scol] != "")]
                        sector_map = dict(zip(sdf[tcol], sdf[scol]))
                except Exception as e:
                    print(f"   ⚠️ Could not load fallback sector mapping CSV: {e}")

        # Fallback: universe industry mapping.
        if not sector_map:
            uni_path = Path("universe/nifty500.csv")
            if uni_path.exists():
                try:
                    udf = pd.read_csv(uni_path)
                    if {'Symbol', 'Industry'}.issubset(udf.columns):
                        udf['ticker'] = udf['Symbol'].astype(str).str.strip() + ".NS"
                        udf['Industry'] = udf['Industry'].astype(str).str.strip()
                        udf = udf[(udf['ticker'] != ".NS") & (udf['Industry'] != "")]
                        sector_map = dict(zip(udf['ticker'], udf['Industry']))
                except Exception as e:
                    print(f"   ⚠️ Could not load universe fallback mapping: {e}")

        print(f"   ✓ Loaded mappings for {len(sector_map)} companies")
        self.sector_map = sector_map
        return sector_map
    
    def load_market_factor(self) -> pd.Series:
        """
        Load market factor (Nifty 50) for market beta control
        
        Returns:
            Series with datetime index and market returns
        """
        print(f"\n📊 Loading market factor (Nifty 50)")
        
        # Try to load Nifty 50 returns
        nifty_sources = [
            Path("data/processed/nifty.parquet"),
            Path("data/processed/index_data/nifty_50.parquet"),
            self.market_data_path / "nifty50_returns.parquet",
            Path("data/market/indices/nifty50.parquet"),
            Path("data/processed/market_returns.parquet")
        ]
        
        for source in nifty_sources:
            if source.exists():
                df = pd.read_parquet(source)
                df = self._ensure_datetime_index(df)
                if df.empty:
                    continue

                low_cols = {str(c).lower(): c for c in df.columns}
                if 'nifty50' in low_cols:
                    market_factor = pd.to_numeric(df[low_cols['nifty50']], errors='coerce')
                elif 'market_return' in low_cols:
                    market_factor = pd.to_numeric(df[low_cols['market_return']], errors='coerce')
                elif 'close' in low_cols:
                    market_factor = pd.to_numeric(df[low_cols['close']], errors='coerce').pct_change(fill_method=None)
                elif 'adj_close' in low_cols:
                    market_factor = pd.to_numeric(df[low_cols['adj_close']], errors='coerce').pct_change(fill_method=None)
                else:
                    market_factor = pd.to_numeric(df.iloc[:, 0], errors='coerce')
                
                print(f"   ✓ Loaded market factor from: {source}")
                self.market_factor = market_factor
                return market_factor
        
        print(f"   ⚠️ Market factor not found, will skip market beta control")
        return None
    
    def align_data(
        self,
        macro_df: pd.DataFrame,
        returns_df: pd.DataFrame,
        market_factor: Optional[pd.Series] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.Series]]:
        """
        Align macro data, returns, and market factor to common frequency and date range
        
        Args:
            macro_df: Macro variables DataFrame
            returns_df: Company returns DataFrame
            market_factor: Market factor Series (optional)
        
        Returns:
            Tuple of (aligned_macro, aligned_returns, aligned_market)
        """
        print(f"\n🔄 Aligning data to {self.target_frequency} frequency")

        def _normalize_index(obj):
            if obj is None:
                return None
            out = obj.copy()
            idx = pd.to_datetime(out.index, errors='coerce')
            keep = ~idx.isna()
            out = out.loc[keep]
            idx = idx[keep]

            if self.target_frequency == 'W':
                # Force a canonical weekly anchor (Friday) for both macro and returns.
                idx = idx.to_period('W-FRI').to_timestamp('W-FRI')
            elif self.target_frequency == 'M':
                idx = idx.to_period('M').to_timestamp('M')

            out.index = idx
            if isinstance(out, pd.DataFrame):
                out = out.groupby(out.index).last().sort_index()
            else:
                out = out.groupby(out.index).last().sort_index()
            return out
        
        # Resample returns to target frequency
        if self.target_frequency == 'W':
            returns_resampled = returns_df.resample('W-FRI').sum()  # Weekly returns
        elif self.target_frequency == 'M':
            returns_resampled = returns_df.resample('M').sum()  # Monthly returns
        else:
            returns_resampled = returns_df
        returns_resampled = _normalize_index(returns_resampled)
        
        # Resample macro data
        macro_resampled = rbi_handler.resample_rbi_data(macro_df, self.target_frequency)
        macro_resampled = _normalize_index(macro_resampled)
        
        # Resample market factor if provided
        market_resampled = None
        if market_factor is not None:
            if self.target_frequency == 'W':
                market_resampled = market_factor.resample('W-FRI').sum()
            elif self.target_frequency == 'M':
                market_resampled = market_factor.resample('M').sum()
            else:
                market_resampled = market_factor
            market_resampled = _normalize_index(market_resampled)

        # Align on strict common index to prevent weekday-anchor drift (Fri vs Sun).
        common_index = macro_resampled.index.intersection(returns_resampled.index)
        if market_resampled is not None:
            common_index = common_index.intersection(market_resampled.index)

        macro_aligned = macro_resampled.reindex(common_index).sort_index()
        returns_aligned = returns_resampled.reindex(common_index).sort_index()
        market_aligned = market_resampled.reindex(common_index).sort_index() if market_resampled is not None else None

        if len(common_index) > 0:
            common_start = common_index.min()
            common_end = common_index.max()
        else:
            common_start = None
            common_end = None

        print(f"   ✓ Aligned date range: {common_start} to {common_end}")
        print(f"   ✓ Aligned observations: {len(macro_aligned)}")
        print(f"   ✓ Macro variables: {len(macro_aligned.columns)}")
        print(f"   ✓ Companies: {len(returns_aligned.columns)}")
        
        return macro_aligned, returns_aligned, market_aligned
    
    def load_all(
        self,
        macro_variables: Optional[List[str]] = None,
        tickers: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Load and align all data in one call
        
        Returns:
            Dictionary with keys: 'macro', 'returns', 'market', 'sector_map'
        """
        print("=" * 80)
        print("🚀 MACRO IMPACT ENGINE - DATA LOADING")
        print("=" * 80)
        
        # Load all data
        macro_df = self.load_macro_data(macro_variables)
        returns_df = self.load_company_returns(tickers, start_date, end_date)
        sector_map = self.load_sector_mapping()
        market_factor = self.load_market_factor()
        
        # Align data
        macro_aligned, returns_aligned, market_aligned = self.align_data(
            macro_df, returns_df, market_factor
        )
        
        print("\n" + "=" * 80)
        print("✅ DATA LOADING COMPLETE")
        print("=" * 80)
        
        return {
            'macro': macro_aligned,
            'returns': returns_aligned,
            'market': market_aligned,
            'sector_map': sector_map,
            'macro_unit_conversion_log': dict(self.macro_unit_conversion_log),
            'macro_unit_profile': dict(self.macro_unit_profile),
        }
