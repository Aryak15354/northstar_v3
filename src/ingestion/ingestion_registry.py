"""
IngestionRegistry — Single entry point for all data loading in Northstar V3.

This is the facade that all other modules import from. Instead of importing
individual loaders, every module should import IngestionRegistry and call
the appropriate method.

Usage:
    from src.ingestion import IngestionRegistry
    
    registry = IngestionRegistry(config)
    prices = registry.market.load(as_of_date=today, tickers=['RELIANCE', 'TCS'])
    fundamentals = registry.fundamentals.load_financials(as_of_date=today)
    macro = registry.macro.load_rbi_data(as_of_date=today)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import yaml

from .market_loader import MarketLoader
from .fundamental_loader import FundamentalLoader
from .macro_loader import MacroLoader
from .alternative_loader import AlternativeDataLoader
from .sentiment_loader import SentimentLoader
from .options_loader import OptionsLoader

logger = logging.getLogger(__name__)


class IngestionRegistry:
    """
    Single entry point for all data loading in Northstar V3.
    
    Provides unified access to all data loaders with consistent configuration.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ingestion registry.
        
        Args:
            config: System configuration dict (if None, loads from config.yaml)
        """
        if config is None:
            config = self._load_default_config()
        
        self.config = config
        
        # Initialize all loaders
        self.market = MarketLoader(config)
        self.fundamentals = FundamentalLoader(config)
        self.macro = MacroLoader(config)
        self.alternative = AlternativeDataLoader(config)
        self.sentiment = SentimentLoader(config)
        self.options = OptionsLoader(config)
        
        logger.info("IngestionRegistry initialized with all loaders")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration from config.yaml."""
        config_paths = [
            Path('config.yaml'),
            Path('config/config.yaml'),
            Path('config/production_upstox.yaml'),
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                    logger.info(f"Loaded config from {config_path}")
                    return config or {}
                except Exception as e:
                    logger.warning(f"Error loading {config_path}: {e}")
        
        logger.warning("No config file found, using empty config")
        return {}

    
    def health_check(self, as_of_date: datetime) -> Dict[str, Dict[str, Any]]:
        """
        Run freshness and availability check across all data sources.
        
        Args:
            as_of_date: Date to check data availability for
            
        Returns:
            Dict with status for each data source:
            {source_name: {status, last_updated, is_fresh, warning}}
        """
        results = {}
        
        # Check market data
        try:
            market_df = self.market.load(as_of_date, tickers=['RELIANCE'])
            if not market_df.empty:
                latest_date = market_df.index.get_level_values('Date').max()
                age_days = (as_of_date.date() - latest_date.date()).days if hasattr(latest_date, 'date') else 999
                
                results['market_data'] = {
                    'status': 'available',
                    'last_updated': str(latest_date),
                    'is_fresh': age_days <= 2,
                    'warning': f"Data is {age_days} days old" if age_days > 2 else None
                }
            else:
                results['market_data'] = {
                    'status': 'unavailable',
                    'last_updated': None,
                    'is_fresh': False,
                    'warning': 'No market data found'
                }
        except Exception as e:
            results['market_data'] = {
                'status': 'error',
                'last_updated': None,
                'is_fresh': False,
                'warning': str(e)
            }
        
        # Check fundamentals
        try:
            fund_df = self.fundamentals.load_financials(as_of_date, tickers=['RELIANCE'])
            results['fundamentals'] = {
                'status': 'available' if not fund_df.empty else 'unavailable',
                'last_updated': str(fund_df.index.get_level_values('ReportDate').max()) if not fund_df.empty else None,
                'is_fresh': not fund_df.empty,
                'warning': None if not fund_df.empty else 'No fundamental data found'
            }
        except Exception as e:
            results['fundamentals'] = {
                'status': 'error',
                'last_updated': None,
                'is_fresh': False,
                'warning': str(e)
            }
        
        # Check macro data
        try:
            macro_df = self.macro.load_rbi_data(as_of_date)
            results['macro_data'] = {
                'status': 'available' if not macro_df.empty else 'unavailable',
                'last_updated': str(macro_df['period_date'].max()) if not macro_df.empty and 'period_date' in macro_df.columns else None,
                'is_fresh': not macro_df.empty,
                'warning': None if not macro_df.empty else 'No macro data found'
            }
        except Exception as e:
            results['macro_data'] = {
                'status': 'error',
                'last_updated': None,
                'is_fresh': False,
                'warning': str(e)
            }
        
        # Check alternative data
        try:
            alt_data = self.alternative.load_all_alternative(as_of_date)
            available_sources = sum(1 for df in alt_data.values() if not df.empty)
            results['alternative_data'] = {
                'status': 'partial' if available_sources > 0 else 'unavailable',
                'last_updated': None,
                'is_fresh': available_sources >= 3,
                'warning': f"Only {available_sources}/5 sources available" if available_sources < 5 else None
            }
        except Exception as e:
            results['alternative_data'] = {
                'status': 'error',
                'last_updated': None,
                'is_fresh': False,
                'warning': str(e)
            }
        
        # Check sentiment
        try:
            is_fresh = self.sentiment.is_sentiment_fresh(as_of_date)
            results['sentiment'] = {
                'status': 'available' if is_fresh else 'stale',
                'last_updated': None,
                'is_fresh': is_fresh,
                'warning': 'Sentiment data is stale' if not is_fresh else None
            }
        except Exception as e:
            results['sentiment'] = {
                'status': 'error',
                'last_updated': None,
                'is_fresh': False,
                'warning': str(e)
            }
        
        return results
    
    def get_data_lineage_report(self, as_of_date: datetime) -> Dict[str, Any]:
        """
        Generate data lineage report for audit and debugging.
        
        Args:
            as_of_date: Date to generate report for
            
        Returns:
            Dict with data availability and quality metrics
        """
        report = {
            'as_of_date': as_of_date.isoformat(),
            'generated_at': datetime.now().isoformat(),
            'data_sources': {}
        }
        
        # Market data lineage
        try:
            universe = self.market.get_universe_as_of(as_of_date)
            market_df = self.market.load(as_of_date)
            
            report['data_sources']['market'] = {
                'universe_size': len(universe),
                'tickers_with_data': len(market_df.index.get_level_values('Ticker').unique()) if not market_df.empty else 0,
                'date_range': {
                    'start': str(market_df.index.get_level_values('Date').min()) if not market_df.empty else None,
                    'end': str(market_df.index.get_level_values('Date').max()) if not market_df.empty else None
                },
                'total_rows': len(market_df)
            }
        except Exception as e:
            report['data_sources']['market'] = {'error': str(e)}
        
        # Fundamentals lineage
        try:
            fund_df = self.fundamentals.load_financials(as_of_date)
            report['data_sources']['fundamentals'] = {
                'tickers_with_data': len(fund_df.index.get_level_values('Ticker').unique()) if not fund_df.empty else 0,
                'total_filings': len(fund_df),
                'latest_filing': str(fund_df.index.get_level_values('ReportDate').max()) if not fund_df.empty else None
            }
        except Exception as e:
            report['data_sources']['fundamentals'] = {'error': str(e)}
        
        # Macro lineage
        try:
            macro_df = self.macro.load_rbi_data(as_of_date)
            report['data_sources']['macro'] = {
                'indicators_available': len([c for c in macro_df.columns if c not in ['period_date', 'release_date']]),
                'total_rows': len(macro_df)
            }
        except Exception as e:
            report['data_sources']['macro'] = {'error': str(e)}
        
        # Alternative data lineage
        try:
            alt_data = self.alternative.load_all_alternative(as_of_date)
            report['data_sources']['alternative'] = {
                source: {
                    'available': not df.empty,
                    'rows': len(df)
                }
                for source, df in alt_data.items()
            }
        except Exception as e:
            report['data_sources']['alternative'] = {'error': str(e)}
        
        return report
    
    def clear_all_caches(self) -> None:
        """Clear caches for all loaders."""
        self.market.clear_cache()
        self.fundamentals.clear_cache()
        self.macro.clear_cache()
        self.alternative.clear_cache()
        self.sentiment.clear_cache()
        self.options.clear_cache()
        logger.info("Cleared all loader caches")
