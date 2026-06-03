"""
Stock Options Configuration Loader

Loads stock options mapping from YAML configuration.
Provides utilities to work with stock options.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StockInfo:
    """Stock information"""
    symbol: str
    isin: str
    name: str
    lot_size: int
    sector: str
    instrument_key: str  # NSE_EQ|ISIN format
    
    @property
    def display_name(self) -> str:
        """Get display name"""
        return f"{self.symbol} ({self.name})"


class StockOptionsLoader:
    """Loads and manages stock options configuration"""
    
    def __init__(self, config_path: str = "config/stock_options_mapping_complete.yaml"):
        """
        Initialize stock options loader
        
        Args:
            config_path: Path to stock options mapping YAML file
        """
        self.config_path = Path(config_path)
        self.stocks: Dict[str, StockInfo] = {}
        self.selection_criteria = {}
        self.recommended_for_beginners = []
        self.high_volatility = []
        
        self._load_config()
        
        logger.info(f"Loaded {len(self.stocks)} stocks with options")
    
    def _load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            logger.warning(f"Stock options config not found: {self.config_path}")
            return
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Load stocks
        stocks_config = config.get('stocks', {})
        for symbol, info in stocks_config.items():
            isin = info.get('isin')
            if not isin:
                logger.warning(f"No ISIN for {symbol}, skipping")
                continue
            
            instrument_key = f"NSE_EQ|{isin}"
            
            self.stocks[symbol] = StockInfo(
                symbol=symbol,
                isin=isin,
                name=info.get('name', symbol),
                lot_size=info.get('lot_size', 0),
                sector=info.get('sector', 'Unknown'),
                instrument_key=instrument_key
            )
        
        # Load selection criteria
        self.selection_criteria = config.get('selection_criteria', {})
        
        # Load recommendations
        self.recommended_for_beginners = config.get('recommended_for_beginners', [])
        self.high_volatility = config.get('high_volatility', [])
    
    def get_stock(self, symbol: str) -> Optional[StockInfo]:
        """
        Get stock information by symbol
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE')
        
        Returns:
            StockInfo or None if not found
        """
        return self.stocks.get(symbol)
    
    def get_all_symbols(self) -> List[str]:
        """Get list of all available stock symbols"""
        return list(self.stocks.keys())
    
    def get_by_sector(self, sector: str) -> List[StockInfo]:
        """
        Get all stocks in a sector
        
        Args:
            sector: Sector name (e.g., 'Banking', 'IT')
        
        Returns:
            List of StockInfo
        """
        return [
            stock for stock in self.stocks.values()
            if stock.sector.lower() == sector.lower()
        ]
    
    def get_recommended_for_beginners(self) -> List[StockInfo]:
        """Get stocks recommended for beginners (highest liquidity)"""
        return [
            self.stocks[symbol] for symbol in self.recommended_for_beginners
            if symbol in self.stocks
        ]
    
    def get_high_volatility_stocks(self) -> List[StockInfo]:
        """Get high volatility stocks"""
        return [
            self.stocks[symbol] for symbol in self.high_volatility
            if symbol in self.stocks
        ]
    
    def get_instrument_key(self, symbol: str) -> Optional[str]:
        """
        Get Upstox instrument key for a stock
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Instrument key (NSE_EQ|ISIN) or None
        """
        stock = self.get_stock(symbol)
        return stock.instrument_key if stock else None
    
    def get_lot_size(self, symbol: str) -> int:
        """
        Get lot size for a stock
        
        Args:
            symbol: Stock symbol
        
        Returns:
            Lot size or 0 if not found
        """
        stock = self.get_stock(symbol)
        return stock.lot_size if stock else 0
    
    def get_sectors(self) -> List[str]:
        """Get list of all sectors"""
        sectors = set(stock.sector for stock in self.stocks.values())
        return sorted(sectors)
    
    def search_stocks(self, query: str) -> List[StockInfo]:
        """
        Search stocks by symbol or name
        
        Args:
            query: Search query
        
        Returns:
            List of matching StockInfo
        """
        query = query.lower()
        results = []
        
        for stock in self.stocks.values():
            if (query in stock.symbol.lower() or 
                query in stock.name.lower() or
                query in stock.sector.lower()):
                results.append(stock)
        
        return results


# Global instance
_stock_loader = None


def get_stock_loader() -> StockOptionsLoader:
    """Get global stock options loader instance"""
    global _stock_loader
    if _stock_loader is None:
        _stock_loader = StockOptionsLoader()
    return _stock_loader


if __name__ == "__main__":
    # Test the loader
    import logging
    logging.basicConfig(level=logging.INFO)
    
    loader = get_stock_loader()
    
    print(f"\nTotal stocks: {len(loader.get_all_symbols())}")
    print(f"Sectors: {loader.get_sectors()}")
    
    print(f"\nRecommended for beginners:")
    for stock in loader.get_recommended_for_beginners():
        print(f"  {stock.symbol:15} - {stock.name:40} Lot: {stock.lot_size}")
    
    print(f"\nHigh volatility stocks:")
    for stock in loader.get_high_volatility_stocks():
        print(f"  {stock.symbol:15} - {stock.name:40} Lot: {stock.lot_size}")
    
    print(f"\nBanking sector:")
    for stock in loader.get_by_sector('Banking'):
        print(f"  {stock.symbol:15} - {stock.name:40} Lot: {stock.lot_size}")
