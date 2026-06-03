#!/usr/bin/env python3
"""
🌍 MARKET CONFIGURATION SYSTEM - TASK 14.1
Configurable Market Parameters to Replace Hardcoded Assumptions

This replaces all hardcoded market assumptions with configurable parameters
that can be adapted to any market globally.

SYSTEM LAWS ENFORCED:
- Invariant C1: Single Source of Truth for Market Configuration
- Invariant C4: Market Adaptability - system works for any market
- Invariant C5: Currency Consistency - all currency handling is consistent

These are not suggestions - they are LAWS that enable global deployment.
"""

import os
import sys
import yaml
from datetime import datetime, time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class MarketType(Enum):
    """Types of markets supported"""
    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    FOREX = "forex"
    CRYPTO = "crypto"

class TradingSession(Enum):
    """Trading session types"""
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    EXTENDED = "extended"

@dataclass
class TradingHours:
    """Trading hours configuration"""
    pre_market_open: Optional[time] = None
    market_open: time = time(9, 0)
    market_close: time = time(16, 0)
    post_market_close: Optional[time] = None
    timezone: str = "UTC"
    
    def is_market_open(self, current_time: datetime) -> bool:
        """Check if market is currently open"""
        current_time_only = current_time.time()
        
        # Check regular trading hours
        if self.market_open <= current_time_only <= self.market_close:
            return True
        
        # Check pre-market hours
        if self.pre_market_open and self.pre_market_open <= current_time_only < self.market_open:
            return True
        
        # Check post-market hours
        if self.post_market_close and self.market_close < current_time_only <= self.post_market_close:
            return True
        
        return False

@dataclass
class CurrencyConfiguration:
    """Currency configuration for market"""
    base_currency: str = "USD"
    display_currency: str = "USD"
    supported_currencies: List[str] = field(default_factory=lambda: ["USD"])
    decimal_places: int = 2
    currency_symbol: str = "$"
    
    def format_amount(self, amount: float) -> str:
        """Format amount with currency symbol"""
        return f"{self.currency_symbol}{amount:,.{self.decimal_places}f}"

@dataclass
class DataSourceConfiguration:
    """Data source configuration"""
    primary_provider: str = "default"
    backup_providers: List[str] = field(default_factory=list)
    symbol_suffix: str = ""  # e.g., ".NS" for NSE, ".L" for LSE
    price_feed_url: Optional[str] = None
    fundamental_data_url: Optional[str] = None
    
    def format_symbol(self, base_symbol: str) -> str:
        """Format symbol with market suffix"""
        return f"{base_symbol}{self.symbol_suffix}"

@dataclass
class RiskConfiguration:
    """Market-specific risk configuration"""
    max_position_size: float = 0.08
    max_sector_exposure: float = 0.30
    volatility_threshold: float = 0.25
    correlation_threshold: float = 0.70
    liquidity_threshold: float = 1000000  # Minimum daily volume
    market_cap_threshold: float = 100000000  # Minimum market cap
    
    def validate_position_size(self, position_size: float) -> bool:
        """Validate position size against limits"""
        return 0 < position_size <= self.max_position_size

@dataclass
class MarketConfiguration:
    """Complete market configuration"""
    # Basic market information
    market_name: str = "default"
    market_code: str = "DEFAULT"
    country: str = "US"
    market_type: MarketType = MarketType.EQUITY
    
    # Trading configuration
    trading_hours: TradingHours = field(default_factory=TradingHours)
    trading_days: List[str] = field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    holidays: List[str] = field(default_factory=list)
    
    # Currency configuration
    currency: CurrencyConfiguration = field(default_factory=CurrencyConfiguration)
    
    # Data sources
    data_sources: DataSourceConfiguration = field(default_factory=DataSourceConfiguration)
    
    # Risk parameters
    risk_parameters: RiskConfiguration = field(default_factory=RiskConfiguration)
    
    # Sector classifications
    sector_classifications: List[str] = field(default_factory=lambda: [
        "TECHNOLOGY", "HEALTHCARE", "FINANCIALS", "CONSUMER_DISCRETIONARY",
        "CONSUMER_STAPLES", "INDUSTRIALS", "ENERGY", "MATERIALS",
        "UTILITIES", "REAL_ESTATE", "COMMUNICATION_SERVICES"
    ])
    
    # Benchmark indices
    benchmark_indices: Dict[str, str] = field(default_factory=lambda: {
        "primary": "SPY",
        "broad_market": "VTI",
        "risk_free": "SHY"
    })
    
    # File paths (configurable)
    data_paths: Dict[str, str] = field(default_factory=lambda: {
        "raw_data": "data/raw",
        "processed_data": "data/processed",
        "validation_data": "data/validation",
        "reports": "reports",
        "logs": "logs",
        "config": "config"
    })
    
    def validate_configuration(self) -> List[str]:
        """Validate market configuration completeness"""
        errors = []
        
        # Required fields
        if not self.market_name:
            errors.append("Market name is required")
        
        if not self.market_code:
            errors.append("Market code is required")
        
        if not self.currency.base_currency:
            errors.append("Base currency is required")
        
        # Trading hours validation
        if self.trading_hours.market_open >= self.trading_hours.market_close:
            errors.append("Market open time must be before market close time")
        
        # Risk parameters validation
        if self.risk_parameters.max_position_size <= 0 or self.risk_parameters.max_position_size > 1:
            errors.append("Max position size must be between 0 and 1")
        
        if self.risk_parameters.max_sector_exposure <= 0 or self.risk_parameters.max_sector_exposure > 1:
            errors.append("Max sector exposure must be between 0 and 1")
        
        return errors
    
    def get_data_path(self, path_type: str, filename: str = "") -> str:
        """Get full path for data file"""
        base_path = self.data_paths.get(path_type, f"data/{path_type}")
        if filename:
            return os.path.join(base_path, filename)
        return base_path
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if given date is a trading day"""
        day_name = date.strftime("%A")
        
        # Check if it's a weekend
        if day_name not in self.trading_days:
            return False
        
        # Check if it's a holiday
        date_str = date.strftime("%Y-%m-%d")
        if date_str in self.holidays:
            return False
        
        return True

class MarketConfigurationManager:
    """
    Manager for market configurations with global support
    
    Replaces hardcoded market assumptions with configurable parameters
    """
    
    def __init__(self, config_dir: str = "config/markets"):
        self.config_dir = config_dir
        self.configurations: Dict[str, MarketConfiguration] = {}
        self.active_market: Optional[str] = None
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Load default configurations
        self._create_default_configurations()
        self._load_configurations()
    
    def _create_default_configurations(self):
        """Create default market configurations"""
        
        # US Market Configuration
        us_config = {
            'market_name': 'United States',
            'market_code': 'US',
            'country': 'US',
            'market_type': 'equity',
            'trading_hours': {
                'pre_market_open': '04:00',
                'market_open': '09:30',
                'market_close': '16:00',
                'post_market_close': '20:00',
                'timezone': 'America/New_York'
            },
            'currency': {
                'base_currency': 'USD',
                'display_currency': 'USD',
                'supported_currencies': ['USD'],
                'decimal_places': 2,
                'currency_symbol': '$'
            },
            'data_sources': {
                'primary_provider': 'yahoo',
                'backup_providers': ['alpha_vantage', 'iex'],
                'symbol_suffix': '',
                'price_feed_url': 'https://finance.yahoo.com',
                'fundamental_data_url': 'https://financialmodelingprep.com'
            },
            'benchmark_indices': {
                'primary': 'SPY',
                'broad_market': 'VTI',
                'risk_free': 'SHY'
            }
        }
        
        # Indian Market Configuration (to replace hardcoded references)
        india_config = {
            'market_name': 'India',
            'market_code': 'IN',
            'country': 'IN',
            'market_type': 'equity',
            'trading_hours': {
                'pre_market_open': '09:00',
                'market_open': '09:15',
                'market_close': '15:30',
                'post_market_close': '16:00',
                'timezone': 'Asia/Kolkata'
            },
            'currency': {
                'base_currency': 'INR',
                'display_currency': 'INR',
                'supported_currencies': ['INR', 'USD'],
                'decimal_places': 2,
                'currency_symbol': '₹'
            },
            'data_sources': {
                'primary_provider': 'nse',
                'backup_providers': ['bse', 'yahoo'],
                'symbol_suffix': '.NS',
                'price_feed_url': 'https://www.nseindia.com',
                'fundamental_data_url': 'https://www.bseindia.com'
            },
            'benchmark_indices': {
                'primary': 'NIFTY50',
                'broad_market': 'NIFTY500',
                'risk_free': 'GSEC10YR'
            },
            'sector_classifications': [
                'TECHNOLOGY', 'PHARMACEUTICALS', 'BANKING', 'AUTOMOBILES',
                'FMCG', 'METALS', 'OIL_GAS', 'TELECOM', 'POWER', 'REALTY'
            ]
        }
        
        # European Market Configuration
        europe_config = {
            'market_name': 'Europe',
            'market_code': 'EU',
            'country': 'EU',
            'market_type': 'equity',
            'trading_hours': {
                'market_open': '08:00',
                'market_close': '16:30',
                'timezone': 'Europe/London'
            },
            'currency': {
                'base_currency': 'EUR',
                'display_currency': 'EUR',
                'supported_currencies': ['EUR', 'GBP', 'USD'],
                'decimal_places': 2,
                'currency_symbol': '€'
            },
            'data_sources': {
                'primary_provider': 'euronext',
                'backup_providers': ['yahoo', 'bloomberg'],
                'symbol_suffix': '.L',
                'price_feed_url': 'https://www.euronext.com',
                'fundamental_data_url': 'https://www.londonstockexchange.com'
            },
            'benchmark_indices': {
                'primary': 'EWU',
                'broad_market': 'VGK',
                'risk_free': 'IEAG'
            }
        }
        
        # Save default configurations
        configs = {
            'us': us_config,
            'india': india_config,
            'europe': europe_config
        }
        
        for market_code, config in configs.items():
            config_file = os.path.join(self.config_dir, f"{market_code}.yaml")
            if not os.path.exists(config_file):
                with open(config_file, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
                print(f"📝 Created default configuration: {config_file}")
    
    def _load_configurations(self):
        """Load all market configurations from config directory"""
        if not os.path.exists(self.config_dir):
            return
        
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.yaml') or filename.endswith('.yml'):
                market_code = filename.split('.')[0]
                config_file = os.path.join(self.config_dir, filename)
                
                try:
                    with open(config_file, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    # Convert to MarketConfiguration object
                    config = self._dict_to_market_config(config_data)
                    self.configurations[market_code] = config
                    
                    print(f"📋 Loaded market configuration: {market_code}")
                    
                except Exception as e:
                    print(f"⚠️ Error loading configuration {config_file}: {e}")
    
    def _dict_to_market_config(self, config_data: Dict[str, Any]) -> MarketConfiguration:
        """Convert dictionary to MarketConfiguration object"""
        
        # Parse trading hours
        trading_hours_data = config_data.get('trading_hours', {})
        trading_hours = TradingHours(
            pre_market_open=self._parse_time(trading_hours_data.get('pre_market_open')),
            market_open=self._parse_time(trading_hours_data.get('market_open', '09:00')),
            market_close=self._parse_time(trading_hours_data.get('market_close', '16:00')),
            post_market_close=self._parse_time(trading_hours_data.get('post_market_close')),
            timezone=trading_hours_data.get('timezone', 'UTC')
        )
        
        # Parse currency configuration
        currency_data = config_data.get('currency', {})
        currency = CurrencyConfiguration(
            base_currency=currency_data.get('base_currency', 'USD'),
            display_currency=currency_data.get('display_currency', 'USD'),
            supported_currencies=currency_data.get('supported_currencies', ['USD']),
            decimal_places=currency_data.get('decimal_places', 2),
            currency_symbol=currency_data.get('currency_symbol', '$')
        )
        
        # Parse data sources
        data_sources_data = config_data.get('data_sources', {})
        data_sources = DataSourceConfiguration(
            primary_provider=data_sources_data.get('primary_provider', 'default'),
            backup_providers=data_sources_data.get('backup_providers', []),
            symbol_suffix=data_sources_data.get('symbol_suffix', ''),
            price_feed_url=data_sources_data.get('price_feed_url'),
            fundamental_data_url=data_sources_data.get('fundamental_data_url')
        )
        
        # Parse risk configuration
        risk_data = config_data.get('risk_parameters', {})
        risk_parameters = RiskConfiguration(
            max_position_size=risk_data.get('max_position_size', 0.08),
            max_sector_exposure=risk_data.get('max_sector_exposure', 0.30),
            volatility_threshold=risk_data.get('volatility_threshold', 0.25),
            correlation_threshold=risk_data.get('correlation_threshold', 0.70),
            liquidity_threshold=risk_data.get('liquidity_threshold', 1000000),
            market_cap_threshold=risk_data.get('market_cap_threshold', 100000000)
        )
        
        return MarketConfiguration(
            market_name=config_data.get('market_name', 'default'),
            market_code=config_data.get('market_code', 'DEFAULT'),
            country=config_data.get('country', 'US'),
            market_type=MarketType(config_data.get('market_type', 'equity')),
            trading_hours=trading_hours,
            trading_days=config_data.get('trading_days', ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]),
            holidays=config_data.get('holidays', []),
            currency=currency,
            data_sources=data_sources,
            risk_parameters=risk_parameters,
            sector_classifications=config_data.get('sector_classifications', []),
            benchmark_indices=config_data.get('benchmark_indices', {}),
            data_paths=config_data.get('data_paths', {})
        )
    
    def _parse_time(self, time_str: Optional[str]) -> Optional[time]:
        """Parse time string to time object"""
        if not time_str:
            return None
        
        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour, minute)
        except:
            return None
    
    def set_active_market(self, market_code: str) -> bool:
        """Set the active market configuration"""
        if market_code in self.configurations:
            self.active_market = market_code
            print(f"🌍 Active market set to: {market_code}")
            return True
        else:
            print(f"❌ Market configuration not found: {market_code}")
            return False
    
    def get_active_config(self) -> Optional[MarketConfiguration]:
        """Get the active market configuration"""
        if self.active_market and self.active_market in self.configurations:
            return self.configurations[self.active_market]
        return None
    
    def get_config(self, market_code: str) -> Optional[MarketConfiguration]:
        """Get specific market configuration"""
        return self.configurations.get(market_code)
    
    def list_markets(self) -> List[str]:
        """List all available market configurations"""
        return list(self.configurations.keys())
    
    def validate_all_configurations(self) -> Dict[str, List[str]]:
        """Validate all market configurations"""
        validation_results = {}
        
        for market_code, config in self.configurations.items():
            errors = config.validate_configuration()
            validation_results[market_code] = errors
        
        return validation_results

# Global market configuration manager instance
_market_config_manager = None

def get_market_config_manager() -> MarketConfigurationManager:
    """Get global market configuration manager instance"""
    global _market_config_manager
    if _market_config_manager is None:
        _market_config_manager = MarketConfigurationManager()
    return _market_config_manager

def get_active_market_config() -> Optional[MarketConfiguration]:
    """Get active market configuration"""
    manager = get_market_config_manager()
    return manager.get_active_config()

def set_active_market(market_code: str) -> bool:
    """Set active market"""
    manager = get_market_config_manager()
    return manager.set_active_market(market_code)

def main():
    """Test the market configuration system"""
    
    print("🌍 TESTING MARKET CONFIGURATION SYSTEM")
    print("=" * 60)
    
    # Create market configuration manager
    manager = MarketConfigurationManager()
    
    # List available markets
    markets = manager.list_markets()
    print(f"\n📋 Available markets: {markets}")
    
    # Test US market configuration
    print(f"\n🇺🇸 Testing US market configuration...")
    manager.set_active_market('us')
    us_config = manager.get_active_config()
    
    if us_config:
        print(f"   Market: {us_config.market_name}")
        print(f"   Currency: {us_config.currency.base_currency}")
        print(f"   Trading hours: {us_config.trading_hours.market_open} - {us_config.trading_hours.market_close}")
        print(f"   Symbol suffix: '{us_config.data_sources.symbol_suffix}'")
        print(f"   Primary benchmark: {us_config.benchmark_indices.get('primary', 'N/A')}")
    
    # Test Indian market configuration
    print(f"\n🇮🇳 Testing Indian market configuration...")
    manager.set_active_market('india')
    india_config = manager.get_active_config()
    
    if india_config:
        print(f"   Market: {india_config.market_name}")
        print(f"   Currency: {india_config.currency.base_currency} ({india_config.currency.currency_symbol})")
        print(f"   Trading hours: {india_config.trading_hours.market_open} - {india_config.trading_hours.market_close}")
        print(f"   Symbol suffix: '{india_config.data_sources.symbol_suffix}'")
        print(f"   Primary benchmark: {india_config.benchmark_indices.get('primary', 'N/A')}")
        
        # Test symbol formatting
        test_symbol = india_config.data_sources.format_symbol("RELIANCE")
        print(f"   Symbol formatting: RELIANCE → {test_symbol}")
        
        # Test currency formatting
        test_amount = india_config.currency.format_amount(1000000)
        print(f"   Currency formatting: 1000000 → {test_amount}")
    
    # Validate all configurations
    print(f"\n🔍 Validating all configurations...")
    validation_results = manager.validate_all_configurations()
    
    for market_code, errors in validation_results.items():
        if errors:
            print(f"   ❌ {market_code}: {len(errors)} errors")
            for error in errors:
                print(f"      - {error}")
        else:
            print(f"   ✅ {market_code}: Valid")
    
    print(f"\n✅ Market configuration system test complete!")
    print(f"   Hardcoded market assumptions can now be replaced with configurable parameters")
    
    return True

if __name__ == "__main__":
    main()