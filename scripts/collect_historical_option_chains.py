"""
Historical Option Chain Data Collector

Fetches historical option chain data from Upstox API for backtesting.
Supports all 4 indices + 205 stocks with options.

Usage:
    # Collect last 30 days for all indices
    python scripts/collect_historical_option_chains.py --days 30 --underlying ALL_INDICES
    
    # Collect last 90 days for top liquid stocks
    python scripts/collect_historical_option_chains.py --days 90 --underlying TOP_LIQUID_STOCKS
    
    # Collect specific date range for single stock
    python scripts/collect_historical_option_chains.py \
        --start-date 2024-01-01 \
        --end-date 2024-12-31 \
        --underlying RELIANCE
"""

import os
import sys
import logging
import time
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
import pandas as pd
import pytz
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.config_loader import get_config
from src.options.upstox_adapter import UpstoxAdapter
from src.options.stock_options_loader import get_stock_loader

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/historical_collection.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class HistoricalOptionChainCollector:
    """
    Collects historical option chain data from Upstox API
    
    Features:
    - Fetches option chains for past dates
    - Supports indices and stocks
    - Handles rate limiting
    - Saves to parquet format
    - Validates data quality
    """
    
    def __init__(self):
        """Initialize collector"""
        self.config = get_config()
        self._set_api_credentials()
        self.upstox = UpstoxAdapter(self.config.upstox)
        self.stock_loader = get_stock_loader()
        
        # Output directory
        self.output_dir = Path('data/options/historical')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Historical Option Chain Collector initialized")
    
    def _set_api_credentials(self):
        """Set Upstox API credentials from environment"""
        access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
        if not access_token:
            logger.warning("UPSTOX_ACCESS_TOKEN not in environment, using config")
    
    def collect_historical_data(
        self,
        underlying: str,
        start_date: date,
        end_date: date,
        save_incremental: bool = True
    ) -> pd.DataFrame:
        """
        Collect historical option chain data for date range
        
        Args:
            underlying: Symbol (index or stock)
            start_date: Start date
            end_date: End date
            save_incremental: Save after each day (recommended for long ranges)
        
        Returns:
            DataFrame with all collected data
        """
        logger.info(f"Collecting historical data for {underlying}")
        logger.info(f"Date range: {start_date} to {end_date}")
        
        # Get instrument key for stocks
        stock_info = self.stock_loader.get_stock(underlying)
        instrument_key = stock_info.instrument_key if stock_info else None
        
        all_data = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:  # Saturday=5, Sunday=6
                current_date += timedelta(days=1)
                continue
            
            try:
                logger.info(f"Fetching data for {underlying} on {current_date}")
                
                # Get expiry for this date
                expiry = self._get_expiry_for_date(underlying, current_date, instrument_key)
                
                if expiry:
                    # Fetch option chain
                    option_chain = self.upstox.fetch_option_chain(
                        underlying, 
                        expiry,
                        instrument_key=instrument_key
                    )
                    
                    if not option_chain.empty:
                        # Add date column
                        option_chain['date'] = current_date
                        all_data.append(option_chain)
                        
                        logger.info(f"✓ Collected {len(option_chain)} contracts for {current_date}")
                        
                        # Save incremental
                        if save_incremental and len(all_data) % 5 == 0:
                            self._save_incremental(underlying, all_data)
                    else:
                        logger.warning(f"Empty option chain for {current_date}")
                else:
                    logger.warning(f"No expiry found for {current_date}")
                
                # Rate limiting - wait 2 seconds between requests
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error fetching data for {current_date}: {e}")
                # Continue with next date
            
            current_date += timedelta(days=1)
        
        # Combine all data
        if all_data:
            df = pd.concat(all_data, ignore_index=True)
            logger.info(f"Collected total {len(df)} records for {underlying}")
            
            # Save final
            self._save_final(underlying, df)
            
            return df
        else:
            logger.warning(f"No data collected for {underlying}")
            return pd.DataFrame()
    
    def _get_expiry_for_date(
        self,
        underlying: str,
        trade_date: date,
        instrument_key: Optional[str] = None
    ) -> Optional[date]:
        """
        Get appropriate expiry for a historical date
        
        For historical data, we want the nearest weekly/monthly expiry
        that was available on that date.
        """
        try:
            # Get instrument key
            if instrument_key is None:
                instrument_key = self.upstox.instrument_key_map.get(underlying)
                if not instrument_key:
                    return None
            
            # Fetch available contracts (this gives us current expiries)
            # For historical, we approximate by finding next Thursday/month-end
            
            # For indices: weekly expiry (Thursday)
            if underlying in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']:
                # Find next Thursday from trade_date
                days_until_thursday = (3 - trade_date.weekday()) % 7
                if days_until_thursday == 0:
                    days_until_thursday = 7
                expiry = trade_date + timedelta(days=days_until_thursday)
                return expiry
            
            # For stocks: monthly expiry (last Thursday of month)
            else:
                # Find last Thursday of current month
                # Start from end of month and work backwards
                year = trade_date.year
                month = trade_date.month
                
                # Last day of month
                if month == 12:
                    last_day = date(year + 1, 1, 1) - timedelta(days=1)
                else:
                    last_day = date(year, month + 1, 1) - timedelta(days=1)
                
                # Find last Thursday
                while last_day.weekday() != 3:  # Thursday = 3
                    last_day -= timedelta(days=1)
                
                # If last Thursday is before trade_date, use next month
                if last_day < trade_date:
                    if month == 12:
                        next_month = date(year + 1, 1, 1)
                    else:
                        next_month = date(year, month + 1, 1)
                    
                    # Last day of next month
                    if next_month.month == 12:
                        last_day = date(next_month.year + 1, 1, 1) - timedelta(days=1)
                    else:
                        last_day = date(next_month.year, next_month.month + 1, 1) - timedelta(days=1)
                    
                    # Find last Thursday
                    while last_day.weekday() != 3:
                        last_day -= timedelta(days=1)
                
                return last_day
        
        except Exception as e:
            logger.error(f"Error getting expiry for {trade_date}: {e}")
            return None
    
    def _save_incremental(self, underlying: str, data_list: List[pd.DataFrame]):
        """Save incremental progress"""
        if not data_list:
            return
        
        df = pd.concat(data_list, ignore_index=True)
        temp_file = self.output_dir / f"{underlying.lower()}_temp.parquet"
        df.to_parquet(temp_file, index=False)
        logger.debug(f"Saved incremental data to {temp_file}")
    
    def _save_final(self, underlying: str, df: pd.DataFrame):
        """Save final collected data"""
        if df.empty:
            return
        
        # Sort by date
        df = df.sort_values(['date', 'expiry', 'strike', 'option_type'])
        
        # Save to parquet
        output_file = self.output_dir / f"{underlying.lower()}_option_chains.parquet"
        df.to_parquet(output_file, index=False)
        
        logger.info(f"Saved {len(df)} records to {output_file}")
        
        # Generate summary
        self._generate_summary(underlying, df)
    
    def _generate_summary(self, underlying: str, df: pd.DataFrame):
        """Generate collection summary"""
        summary_file = self.output_dir / f"{underlying.lower()}_summary.txt"
        
        with open(summary_file, 'w') as f:
            f.write(f"Historical Option Chain Data Summary\n")
            f.write(f"=" * 60 + "\n\n")
            f.write(f"Underlying: {underlying}\n")
            f.write(f"Total Records: {len(df):,}\n")
            f.write(f"Date Range: {df['date'].min()} to {df['date'].max()}\n")
            f.write(f"Trading Days: {df['date'].nunique()}\n")
            f.write(f"Unique Expiries: {df['expiry'].nunique()}\n")
            f.write(f"Unique Strikes: {df['strike'].nunique()}\n")
            f.write(f"\nData Quality:\n")
            f.write(f"  Missing IV: {df['iv'].isna().sum()}\n")
            f.write(f"  Missing Greeks: {df['delta'].isna().sum()}\n")
            f.write(f"  Zero OI: {(df['oi'] == 0).sum()}\n")
            f.write(f"\nFile Size: {(self.output_dir / f'{underlying.lower()}_option_chains.parquet').stat().st_size / 1024 / 1024:.2f} MB\n")
        
        logger.info(f"Summary saved to {summary_file}")
    
    def collect_multiple_underlyings(
        self,
        underlyings: List[str],
        start_date: date,
        end_date: date
    ):
        """
        Collect data for multiple underlyings
        
        Args:
            underlyings: List of symbols
            start_date: Start date
            end_date: End date
        """
        logger.info(f"Collecting data for {len(underlyings)} underlyings")
        
        results = {}
        
        for i, underlying in enumerate(underlyings, 1):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Progress: {i}/{len(underlyings)} - {underlying}")
            logger.info(f"{'=' * 60}")
            
            try:
                df = self.collect_historical_data(
                    underlying=underlying,
                    start_date=start_date,
                    end_date=end_date,
                    save_incremental=True
                )
                
                results[underlying] = {
                    'success': True,
                    'records': len(df),
                    'days': df['date'].nunique() if not df.empty else 0
                }
                
            except Exception as e:
                logger.error(f"Failed to collect data for {underlying}: {e}")
                results[underlying] = {
                    'success': False,
                    'error': str(e)
                }
            
            # Wait between underlyings to respect rate limits
            if i < len(underlyings):
                logger.info("Waiting 10 seconds before next underlying...")
                time.sleep(10)
        
        # Generate overall summary
        self._generate_collection_report(results, start_date, end_date)
    
    def _generate_collection_report(
        self,
        results: dict,
        start_date: date,
        end_date: date
    ):
        """Generate overall collection report"""
        report_file = self.output_dir / f"collection_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w') as f:
            f.write("Historical Option Chain Collection Report\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Collection Date: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}\n")
            f.write(f"Date Range: {start_date} to {end_date}\n")
            f.write(f"Total Underlyings: {len(results)}\n\n")
            
            successful = sum(1 for r in results.values() if r.get('success'))
            failed = len(results) - successful
            
            f.write(f"Success: {successful}\n")
            f.write(f"Failed: {failed}\n\n")
            
            f.write("Details:\n")
            f.write("-" * 80 + "\n")
            
            for underlying, result in sorted(results.items()):
                if result.get('success'):
                    f.write(f"✓ {underlying:20} {result['records']:8,} records  {result['days']:3} days\n")
                else:
                    f.write(f"✗ {underlying:20} Error: {result.get('error', 'Unknown')}\n")
        
        logger.info(f"\nCollection report saved to {report_file}")
        logger.info(f"Successful: {successful}/{len(results)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Collect historical option chain data for backtesting'
    )
    
    # Date range options
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument('--days', type=int,
                           help='Number of days to collect (from today backwards)')
    date_group.add_argument('--start-date', type=str,
                           help='Start date (YYYY-MM-DD)')
    
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD), defaults to today')
    
    # Underlying selection
    parser.add_argument('--underlying', default='ALL_INDICES',
                       help='Underlying to collect. Options: '
                            'ALL_INDICES, ALL_STOCKS, TOP_LIQUID_STOCKS, '
                            'RECOMMENDED_STOCKS, specific symbol, or sector name')
    
    args = parser.parse_args()
    
    # Parse dates
    if args.days:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days)
    else:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        if args.end_date:
            end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
        else:
            end_date = date.today()
    
    # Validate dates
    if start_date > end_date:
        logger.error("Start date must be before end date")
        return 1
    
    if end_date > date.today():
        logger.error("End date cannot be in the future")
        return 1
    
    # Create collector
    collector = HistoricalOptionChainCollector()
    
    # Determine underlyings
    underlyings = []
    
    if args.underlying == 'ALL_INDICES':
        underlyings = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
    
    elif args.underlying == 'ALL_STOCKS':
        underlyings = collector.stock_loader.get_all_symbols()
    
    elif args.underlying == 'TOP_LIQUID_STOCKS':
        underlyings = ['ITC', 'ONGC', 'SBIN', 'NATIONALUM', 'TCS', 'GAIL', 'HINDZINC', 'VEDL',
                      'CANBK', 'LICI', 'TATASTEEL', 'COALINDIA', 'HDFCBANK', 'SAIL', 'WIPRO',
                      'BANKINDIA', 'PIIND', 'RELIANCE', 'SUNPHARMA', 'TIINDIA']
    
    elif args.underlying == 'RECOMMENDED_STOCKS':
        recommended = collector.stock_loader.get_recommended_for_beginners()
        underlyings = [stock.symbol for stock in recommended]
    
    elif args.underlying in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']:
        underlyings = [args.underlying]
    
    elif collector.stock_loader.get_stock(args.underlying):
        underlyings = [args.underlying]
    
    else:
        # Try as sector
        sector_stocks = collector.stock_loader.get_by_sector(args.underlying)
        if sector_stocks:
            underlyings = [stock.symbol for stock in sector_stocks]
        else:
            logger.error(f"Unknown underlying or sector: {args.underlying}")
            return 1
    
    # Collect data
    logger.info(f"\n{'=' * 80}")
    logger.info(f"HISTORICAL OPTION CHAIN DATA COLLECTION")
    logger.info(f"{'=' * 80}")
    logger.info(f"Date Range: {start_date} to {end_date} ({(end_date - start_date).days} days)")
    logger.info(f"Underlyings: {len(underlyings)}")
    logger.info(f"{'=' * 80}\n")
    
    if len(underlyings) == 1:
        # Single underlying
        collector.collect_historical_data(
            underlying=underlyings[0],
            start_date=start_date,
            end_date=end_date
        )
    else:
        # Multiple underlyings
        collector.collect_multiple_underlyings(
            underlyings=underlyings,
            start_date=start_date,
            end_date=end_date
        )
    
    logger.info(f"\n{'=' * 80}")
    logger.info("Collection complete!")
    logger.info(f"Data saved to: {collector.output_dir}")
    logger.info(f"{'=' * 80}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
