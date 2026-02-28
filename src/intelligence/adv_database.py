#!/usr/bin/env python3
"""
ADV Database - Average Daily Volume Data Management

This module provides the foundation for liquidity-constrained position sizing
by managing Average Daily Volume (ADV) data with rolling calculations and
multiple data source support.

Key Features:
- Rolling ADV calculations (21-day, 63-day windows)
- Multiple data source support (market feeds, historical files)
- Graceful handling of missing/stale data
- Liquidity tier classification
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class LiquidityTier(Enum):
    """Liquidity tier classifications based on ADV"""
    LARGE_CAP = "large_cap"      # >$50M ADV
    MID_CAP = "mid_cap"          # $5-50M ADV  
    SMALL_CAP = "small_cap"      # $1-5M ADV
    MICRO_CAP = "micro_cap"      # <$1M ADV (rejected)

@dataclass
class ADVData:
    """ADV data point with metadata"""
    symbol: str
    date: datetime
    adv_21d: float              # 21-day rolling ADV
    adv_63d: float              # 63-day rolling ADV
    adv_126d: float             # 126-day rolling ADV (for stability)
    liquidity_tier: LiquidityTier
    market_cap: Optional[float] = None
    avg_spread: Optional[float] = None
    data_quality: float = 1.0   # 0-1 quality score
    is_stale: bool = False      # Data staleness flag

@dataclass
class ADVConfig:
    """Configuration for ADV calculations"""
    min_adv_threshold: float = 10_000_000    # ₹1 Crore minimum ADV
    large_cap_threshold: float = 500_000_000  # ₹50 Crore for large cap
    mid_cap_threshold: float = 50_000_000     # ₹5 Crore for mid cap
    max_staleness_days: int = 5              # Max days for stale data
    min_data_points: int = 15                # Min points for ADV calculation
    quality_decay_rate: float = 0.1         # Quality decay per day

class ADVDatabase:
    """
    Average Daily Volume database with rolling calculations.
    
    This is the foundation for liquidity-constrained position sizing.
    Provides ADV data with quality metrics and tier classification.
    """
    
    def __init__(self, config: ADVConfig = None):
        self.config = config or ADVConfig()
        self.name = "ADV Database"
        self.version = "1.0"
        
        # Data storage
        self.adv_data: Dict[str, List[ADVData]] = {}
        self.raw_volume_data: Dict[str, pd.DataFrame] = {}
        self.last_update: Dict[str, datetime] = {}
        
        # Caching for performance
        self.adv_cache: Dict[str, ADVData] = {}
        self.cache_expiry: Dict[str, datetime] = {}
        
        print(f"📊 {self.name} initialized")
        print(f"   Min ADV threshold: ₹{self.config.min_adv_threshold:,.0f}")
        print(f"   Large cap threshold: ₹{self.config.large_cap_threshold:,.0f}")
        print(f"   Max staleness: {self.config.max_staleness_days} days")
    
    def add_volume_data(self, 
                       symbol: str, 
                       volume_data: pd.DataFrame,
                       price_data: pd.DataFrame = None) -> None:
        """
        Add raw volume data for a symbol.
        
        Args:
            symbol: Stock symbol
            volume_data: DataFrame with 'date' and 'volume' columns
            price_data: Optional DataFrame with 'date' and 'close' columns
        """
        
        # Validate input data
        required_cols = ['date', 'volume']
        if not all(col in volume_data.columns for col in required_cols):
            raise ValueError(f"Volume data must contain columns: {required_cols}")
        
        # Convert to standard format
        df = volume_data.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Add price data if available
        if price_data is not None:
            price_df = price_data.copy()
            price_df['date'] = pd.to_datetime(price_df['date'])
            df = df.merge(price_df[['date', 'close']], on='date', how='left')
            
            # Calculate dollar volume (ADV in currency units)
            df['dollar_volume'] = df['volume'] * df['close']
        else:
            # Use share volume as proxy (less accurate)
            df['dollar_volume'] = df['volume']
        
        # Store raw data
        self.raw_volume_data[symbol] = df
        self.last_update[symbol] = datetime.now()
        
        # Clear cache for this symbol
        if symbol in self.adv_cache:
            del self.adv_cache[symbol]
            del self.cache_expiry[symbol]
        
        print(f"📊 Added volume data for {symbol}: {len(df)} days")
    
    def calculate_rolling_adv(self, 
                            symbol: str, 
                            as_of_date: datetime = None) -> Optional[ADVData]:
        """
        Calculate rolling ADV for a symbol as of a specific date.
        
        Args:
            symbol: Stock symbol
            as_of_date: Date for calculation (default: latest available)
            
        Returns:
            ADVData object with rolling calculations
        """
        
        if symbol not in self.raw_volume_data:
            return None
        
        # Use cache if available and fresh
        cache_key = f"{symbol}_{as_of_date}"
        if (cache_key in self.adv_cache and 
            cache_key in self.cache_expiry and
            datetime.now() < self.cache_expiry[cache_key]):
            return self.adv_cache[cache_key]
        
        df = self.raw_volume_data[symbol].copy()
        
        # Filter data up to as_of_date
        if as_of_date:
            df = df[df['date'] <= as_of_date]
        
        if len(df) < self.config.min_data_points:
            return None
        
        # Calculate rolling ADVs
        df = df.sort_values('date')
        df['adv_21d'] = df['dollar_volume'].rolling(window=21, min_periods=15).mean()
        df['adv_63d'] = df['dollar_volume'].rolling(window=63, min_periods=30).mean()
        df['adv_126d'] = df['dollar_volume'].rolling(window=126, min_periods=60).mean()
        
        # Get latest values
        latest = df.iloc[-1]
        calculation_date = latest['date']
        
        # Handle missing values
        adv_21d = latest['adv_21d'] if not pd.isna(latest['adv_21d']) else 0.0
        adv_63d = latest['adv_63d'] if not pd.isna(latest['adv_63d']) else adv_21d
        adv_126d = latest['adv_126d'] if not pd.isna(latest['adv_126d']) else adv_63d
        
        # Determine liquidity tier
        primary_adv = adv_21d  # Use 21-day as primary
        liquidity_tier = self._classify_liquidity_tier(primary_adv)
        
        # Calculate data quality
        data_quality = self._calculate_data_quality(symbol, calculation_date)
        
        # Check staleness - only mark as stale if very recent data is old
        days_since_update = (datetime.now() - calculation_date).days
        is_stale = days_since_update > self.config.max_staleness_days and calculation_date > (datetime.now() - timedelta(days=30))
        
        # Create ADV data object
        adv_data = ADVData(
            symbol=symbol,
            date=calculation_date,
            adv_21d=adv_21d,
            adv_63d=adv_63d,
            adv_126d=adv_126d,
            liquidity_tier=liquidity_tier,
            data_quality=data_quality,
            is_stale=is_stale
        )
        
        # Cache result
        self.adv_cache[cache_key] = adv_data
        self.cache_expiry[cache_key] = datetime.now() + timedelta(hours=1)
        
        return adv_data
    
    def _classify_liquidity_tier(self, adv: float) -> LiquidityTier:
        """Classify symbol into liquidity tier based on ADV"""
        
        if adv >= self.config.large_cap_threshold:
            return LiquidityTier.LARGE_CAP
        elif adv >= self.config.mid_cap_threshold:
            return LiquidityTier.MID_CAP
        elif adv >= self.config.min_adv_threshold:
            return LiquidityTier.SMALL_CAP
        else:
            return LiquidityTier.MICRO_CAP
    
    def _calculate_data_quality(self, symbol: str, calculation_date: datetime) -> float:
        """Calculate data quality score (0-1)"""
        
        if symbol not in self.last_update:
            return 0.5  # Default quality for unknown data
        
        # Quality decays with staleness from calculation date, not current date
        # This allows historical analysis without penalizing old data
        days_since_calculation = (datetime.now() - calculation_date).days
        
        # Only penalize if data is very recent but calculation is old
        if days_since_calculation <= self.config.max_staleness_days:
            return 1.0  # Fresh data
        else:
            # Gradual decay for older data
            quality_decay = min((days_since_calculation - self.config.max_staleness_days) * self.config.quality_decay_rate, 0.8)
            base_quality = 1.0
            final_quality = max(base_quality - quality_decay, 0.2)  # Minimum 20% quality
            
            return final_quality
    
    def get_adv_for_symbols(self, 
                          symbols: List[str], 
                          as_of_date: datetime = None) -> Dict[str, Optional[ADVData]]:
        """
        Get ADV data for multiple symbols.
        
        Args:
            symbols: List of stock symbols
            as_of_date: Date for calculation
            
        Returns:
            Dictionary mapping symbols to ADVData objects
        """
        
        results = {}
        
        for symbol in symbols:
            try:
                adv_data = self.calculate_rolling_adv(symbol, as_of_date)
                results[symbol] = adv_data
            except Exception as e:
                print(f"⚠️  Error calculating ADV for {symbol}: {e}")
                results[symbol] = None
        
        return results
    
    def get_liquid_symbols(self, 
                         symbols: List[str], 
                         min_tier: LiquidityTier = LiquidityTier.SMALL_CAP,
                         as_of_date: datetime = None) -> List[str]:
        """
        Filter symbols by minimum liquidity tier.
        
        Args:
            symbols: List of symbols to filter
            min_tier: Minimum liquidity tier required
            as_of_date: Date for calculation
            
        Returns:
            List of symbols meeting liquidity requirements
        """
        
        adv_data = self.get_adv_for_symbols(symbols, as_of_date)
        
        # Define tier hierarchy
        tier_hierarchy = {
            LiquidityTier.LARGE_CAP: 3,
            LiquidityTier.MID_CAP: 2,
            LiquidityTier.SMALL_CAP: 1,
            LiquidityTier.MICRO_CAP: 0
        }
        
        min_tier_value = tier_hierarchy[min_tier]
        liquid_symbols = []
        
        for symbol, data in adv_data.items():
            if data is not None:
                symbol_tier_value = tier_hierarchy[data.liquidity_tier]
                if symbol_tier_value >= min_tier_value and not data.is_stale:
                    liquid_symbols.append(symbol)
        
        return liquid_symbols
    
    def get_database_stats(self) -> Dict:
        """Get database statistics and health metrics"""
        
        total_symbols = len(self.raw_volume_data)
        symbols_with_recent_data = 0
        tier_distribution = {tier: 0 for tier in LiquidityTier}
        
        for symbol in self.raw_volume_data.keys():
            adv_data = self.calculate_rolling_adv(symbol)
            if adv_data and not adv_data.is_stale:
                symbols_with_recent_data += 1
                tier_distribution[adv_data.liquidity_tier] += 1
        
        return {
            'total_symbols': total_symbols,
            'symbols_with_recent_data': symbols_with_recent_data,
            'data_freshness_rate': symbols_with_recent_data / total_symbols if total_symbols > 0 else 0,
            'tier_distribution': {tier.value: count for tier, count in tier_distribution.items()},
            'cache_size': len(self.adv_cache),
            'last_update_count': len(self.last_update)
        }

def main():
    """Test the ADV Database"""
    
    print("🧪 TESTING ADV DATABASE")
    print("=" * 60)
    
    # Initialize database
    config = ADVConfig(
        min_adv_threshold=5_000_000,      # ₹50 Lakh minimum
        large_cap_threshold=250_000_000,  # ₹25 Crore for large cap
        mid_cap_threshold=25_000_000      # ₹2.5 Crore for mid cap
    )
    
    adv_db = ADVDatabase(config)
    
    # Generate test data for Indian market
    np.random.seed(42)
    symbols = ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'SMALLCAP']
    
    for symbol in symbols:
        # Generate volume and price data (use recent dates)
        dates = pd.date_range(start='2025-01-01', end='2026-01-03', freq='D')
        
        # Different volume profiles for Indian symbols (INR values)
        if symbol == 'RELIANCE':
            base_volume = 5_000_000   # High volume large cap
            base_price = 2500         # ~₹2500
        elif symbol == 'TCS':
            base_volume = 2_000_000   # Medium-high volume
            base_price = 3500         # ~₹3500
        elif symbol == 'HDFCBANK':
            base_volume = 3_000_000   # High volume banking
            base_price = 1600         # ~₹1600
        elif symbol == 'INFY':
            base_volume = 4_000_000   # High volume IT
            base_price = 1400         # ~₹1400
        elif symbol == 'SMALLCAP':
            base_volume = 50_000      # Low volume small cap
            base_price = 150          # ~₹150
        else:
            base_volume = 1_000_000   # Medium volume
            base_price = 500          # ~₹500
        
        # Add noise and trends
        volume_noise = np.random.normal(1.0, 0.3, len(dates))
        price_noise = np.random.normal(1.0, 0.1, len(dates))
        
        volume_data = pd.DataFrame({
            'date': dates,
            'volume': base_volume * volume_noise
        })
        
        price_data = pd.DataFrame({
            'date': dates,
            'close': base_price * price_noise
        })
        
        # Add to database
        adv_db.add_volume_data(symbol, volume_data, price_data)
    
    # Test ADV calculations
    print(f"\n📊 TESTING ADV CALCULATIONS")
    print("=" * 40)
    
    test_date = datetime(2026, 1, 3)  # Recent date
    
    for symbol in symbols:
        adv_data = adv_db.calculate_rolling_adv(symbol, test_date)
        
        if adv_data:
            print(f"\n{symbol}:")
            print(f"   21-day ADV: ${adv_data.adv_21d:,.0f}")
            print(f"   63-day ADV: ${adv_data.adv_63d:,.0f}")
            print(f"   Liquidity Tier: {adv_data.liquidity_tier.value}")
            print(f"   Data Quality: {adv_data.data_quality:.2f}")
            print(f"   Is Stale: {adv_data.is_stale}")
        else:
            print(f"\n{symbol}: No ADV data available")
    
    # Test liquidity filtering
    print(f"\n🔍 TESTING LIQUIDITY FILTERING")
    print("=" * 40)
    
    liquid_symbols = adv_db.get_liquid_symbols(
        symbols, 
        min_tier=LiquidityTier.SMALL_CAP,
        as_of_date=test_date
    )
    
    print(f"Symbols meeting small-cap+ liquidity: {liquid_symbols}")
    
    # Database statistics
    print(f"\n📈 DATABASE STATISTICS")
    print("=" * 40)
    
    stats = adv_db.get_database_stats()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"   {sub_key}: {sub_value}")
        else:
            print(f"{key}: {value}")

if __name__ == "__main__":
    main()