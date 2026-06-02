"""
Daily EOD Option Chain Collector

Collects end-of-day option chain data and appends to historical database.
Run this daily (after market close) to build historical data over time.

Schedule with cron:
    # Run at 4:00 PM IST daily (after market close at 3:30 PM)
    0 16 * * 1-5 cd /path/to/northstar_v3 && python scripts/daily_eod_option_chain_collector.py

Usage:
    python scripts/daily_eod_option_chain_collector.py
    python scripts/daily_eod_option_chain_collector.py --underlying ALL_INDICES
    python scripts/daily_eod_option_chain_collector.py --underlying TOP_LIQUID_STOCKS
"""

import os
import sys
import logging
from datetime import datetime, date
from pathlib import Path
import pandas as pd
import pytz

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.config_loader import get_config
from src.options.upstox_adapter import UpstoxAdapter
from src.options.stock_options_loader import get_stock_loader

IST = pytz.timezone('Asia/Kolkata')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/daily_eod_collection.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DailyEODCollector:
    """Collects end-of-day option chain data"""
    
    def __init__(self):
        self.config = get_config()
        self.upstox = UpstoxAdapter(self.config.upstox)
        self.stock_loader = get_stock_loader()
        self.output_dir = Path('data/options/historical')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Daily EOD Collector initialized")
    
    def collect_today(self, underlying: str) -> pd.DataFrame:
        """Collect today's option chain data"""
        today = date.today()
        
        logger.info(f"Collecting EOD data for {underlying} on {today}")
        
        # Get instrument key for stocks
        stock_info = self.stock_loader.get_stock(underlying)
        instrument_key = stock_info.instrument_key if stock_info else None
        
        # Get next expiry
        expiry = self._get_next_expiry(underlying, instrument_key)
        
        if not expiry:
            logger.error(f"Could not determine expiry for {underlying}")
            return pd.DataFrame()
        
        # Fetch option chain
        try:
            option_chain = self.upstox.fetch_option_chain(
                underlying,
                expiry,
                instrument_key=instrument_key
            )
            
            if option_chain.empty:
                logger.warning(f"Empty option chain for {underlying}")
                return pd.DataFrame()
            
            # Add date column
            option_chain['date'] = today
            
            logger.info(f"✓ Collected {len(option_chain)} contracts for {underlying}")
            
            return option_chain
            
        except Exception as e:
            logger.error(f"Error collecting data for {underlying}: {e}")
            return pd.DataFrame()
    
    def _get_next_expiry(self, underlying: str, instrument_key: str = None) -> date:
        """Get next expiry"""
        try:
            if instrument_key is None:
                instrument_key = self.upstox.instrument_key_map.get(underlying)
            
            if not instrument_key:
                return None
            
            url = self.config.upstox.endpoints.get('option_contracts')
            params = {'instrument_key': instrument_key}
            
            response = self.upstox._make_request('GET', url, params=params)
            
            if response.get('status') == 'success' and response.get('data'):
                expiries = set()
                for contract in response['data']:
                    if 'expiry' in contract:
                        expiry_date = datetime.strptime(contract['expiry'], '%Y-%m-%d').date()
                        expiries.add(expiry_date)
                
                if expiries:
                    today = date.today()
                    future_expiries = [e for e in expiries if e > today]
                    if future_expiries:
                        return min(future_expiries)
        
        except Exception as e:
            logger.error(f"Error getting expiry: {e}")
        
        return None
    
    def append_to_historical(self, underlying: str, new_data: pd.DataFrame):
        """Append new data to historical file"""
        if new_data.empty:
            return
        
        file_path = self.output_dir / f"{underlying.lower()}_option_chains.parquet"
        
        if file_path.exists():
            # Load existing data
            existing = pd.read_parquet(file_path)
            
            # Combine and deduplicate
            combined = pd.concat([existing, new_data], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=['date', 'symbol', 'expiry', 'strike', 'option_type'],
                keep='last'
            )
            combined = combined.sort_values(['date', 'expiry', 'strike', 'option_type'])
            
            logger.info(f"Appending to existing file: {len(existing)} + {len(new_data)} = {len(combined)} records")
        else:
            combined = new_data
            logger.info(f"Creating new file with {len(combined)} records")
        
        # Save
        combined.to_parquet(file_path, index=False)
        logger.info(f"Saved to {file_path}")
    
    def collect_multiple(self, underlyings: list):
        """Collect for multiple underlyings"""
        logger.info(f"Collecting EOD data for {len(underlyings)} underlyings")
        
        results = {}
        
        for underlying in underlyings:
            try:
                data = self.collect_today(underlying)
                
                if not data.empty:
                    self.append_to_historical(underlying, data)
                    results[underlying] = {'success': True, 'records': len(data)}
                else:
                    results[underlying] = {'success': False, 'error': 'Empty data'}
            
            except Exception as e:
                logger.error(f"Failed for {underlying}: {e}")
                results[underlying] = {'success': False, 'error': str(e)}
        
        # Summary
        successful = sum(1 for r in results.values() if r.get('success'))
        logger.info(f"\nCollection complete: {successful}/{len(underlyings)} successful")
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect daily EOD option chain data')
    parser.add_argument('--underlying', default='ALL_INDICES',
                       help='Underlying to collect (ALL_INDICES, TOP_LIQUID_STOCKS, etc.)')
    
    args = parser.parse_args()
    
    collector = DailyEODCollector()
    
    # Determine underlyings
    if args.underlying == 'ALL_INDICES':
        underlyings = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
    elif args.underlying == 'TOP_LIQUID_STOCKS':
        underlyings = ['ITC', 'ONGC', 'SBIN', 'NATIONALUM', 'TCS', 'GAIL', 'HINDZINC', 'VEDL',
                      'CANBK', 'LICI', 'TATASTEEL', 'COALINDIA', 'HDFCBANK', 'SAIL', 'WIPRO',
                      'BANKINDIA', 'PIIND', 'RELIANCE', 'SUNPHARMA', 'TIINDIA']
    elif args.underlying == 'ALL_STOCKS':
        underlyings = collector.stock_loader.get_all_symbols()
    else:
        underlyings = [args.underlying]
    
    logger.info(f"\n{'=' * 80}")
    logger.info(f"DAILY EOD COLLECTION - {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
    logger.info(f"{'=' * 80}\n")
    
    collector.collect_multiple(underlyings)
    
    logger.info(f"\n{'=' * 80}")
    logger.info("EOD collection complete!")
    logger.info(f"{'=' * 80}\n")


if __name__ == '__main__':
    main()
