"""
Historical Option Chain Data Validator

Validates collected historical data for quality and completeness.

Usage:
    python scripts/validate_historical_data.py --underlying NIFTY
    python scripts/validate_historical_data.py --underlying ALL_INDICES
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.stock_options_loader import get_stock_loader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class HistoricalDataValidator:
    """Validates historical option chain data"""
    
    def __init__(self, data_dir: str = "data/options/historical"):
        self.data_dir = Path(data_dir)
        self.stock_loader = get_stock_loader()
    
    def validate_underlying(self, underlying: str) -> dict:
        """
        Validate data for a single underlying
        
        Returns:
            dict with validation results
        """
        logger.info(f"Validating data for {underlying}")
        
        # Load data
        file_path = self.data_dir / f"{underlying.lower()}_option_chains.parquet"
        
        if not file_path.exists():
            return {
                'underlying': underlying,
                'status': 'MISSING',
                'error': f'Data file not found: {file_path}'
            }
        
        try:
            df = pd.read_parquet(file_path)
        except Exception as e:
            return {
                'underlying': underlying,
                'status': 'ERROR',
                'error': f'Failed to load data: {e}'
            }
        
        # Run validation checks
        results = {
            'underlying': underlying,
            'status': 'PASS',
            'total_records': len(df),
            'checks': {}
        }
        
        # Check 1: Required columns
        required_cols = [
            'date', 'symbol', 'expiry', 'strike', 'option_type',
            'bid', 'ask', 'ltp', 'iv', 'delta', 'gamma', 'theta', 'vega',
            'oi', 'change_oi', 'volume', 'underlying_price'
        ]
        
        missing_cols = set(required_cols) - set(df.columns)
        results['checks']['required_columns'] = {
            'pass': len(missing_cols) == 0,
            'missing': list(missing_cols) if missing_cols else None
        }
        
        if missing_cols:
            results['status'] = 'FAIL'
            return results
        
        # Check 2: Date range
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['expiry'] = pd.to_datetime(df['expiry']).dt.date
        
        results['checks']['date_range'] = {
            'start': str(df['date'].min()),
            'end': str(df['date'].max()),
            'trading_days': df['date'].nunique(),
            'calendar_days': (df['date'].max() - df['date'].min()).days
        }
        
        # Check 3: Temporal consistency (expiry >= date)
        invalid_expiry = df[df['expiry'] < df['date']]
        results['checks']['temporal_consistency'] = {
            'pass': len(invalid_expiry) == 0,
            'invalid_records': len(invalid_expiry)
        }
        
        if len(invalid_expiry) > 0:
            results['status'] = 'FAIL'
        
        # Check 4: Duplicates
        dup_cols = ['date', 'symbol', 'expiry', 'strike', 'option_type']
        duplicates = df[df.duplicated(subset=dup_cols, keep=False)]
        results['checks']['duplicates'] = {
            'pass': len(duplicates) == 0,
            'duplicate_records': len(duplicates)
        }
        
        if len(duplicates) > 0:
            results['status'] = 'WARN'
        
        # Check 5: Missing values
        missing_iv = df['iv'].isna().sum()
        missing_delta = df['delta'].isna().sum()
        missing_oi = df['oi'].isna().sum()
        
        results['checks']['missing_values'] = {
            'iv': missing_iv,
            'delta': missing_delta,
            'oi': missing_oi,
            'pass': (missing_iv + missing_delta + missing_oi) == 0
        }
        
        if (missing_iv + missing_delta + missing_oi) > len(df) * 0.1:  # >10% missing
            results['status'] = 'WARN'
        
        # Check 6: IV range (should be between 0.05 and 2.0)
        valid_iv = df[(df['iv'] >= 0.05) & (df['iv'] <= 2.0)]
        iv_pass_rate = len(valid_iv) / len(df) * 100
        
        results['checks']['iv_range'] = {
            'pass': iv_pass_rate > 95,
            'valid_percentage': round(iv_pass_rate, 2),
            'min': float(df['iv'].min()),
            'max': float(df['iv'].max()),
            'mean': float(df['iv'].mean())
        }
        
        if iv_pass_rate < 90:
            results['status'] = 'WARN'
        
        # Check 7: Greeks range
        delta_valid = df[(df['delta'].abs() <= 1.0)]
        gamma_valid = df[(df['gamma'] >= 0)]
        
        results['checks']['greeks_range'] = {
            'delta_valid_pct': round(len(delta_valid) / len(df) * 100, 2),
            'gamma_valid_pct': round(len(gamma_valid) / len(df) * 100, 2),
            'pass': len(delta_valid) / len(df) > 0.95 and len(gamma_valid) / len(df) > 0.95
        }
        
        # Check 8: OI distribution
        zero_oi = (df['oi'] == 0).sum()
        results['checks']['oi_distribution'] = {
            'zero_oi_count': int(zero_oi),
            'zero_oi_pct': round(zero_oi / len(df) * 100, 2),
            'mean_oi': float(df['oi'].mean()),
            'median_oi': float(df['oi'].median())
        }
        
        # Check 9: Date gaps (missing trading days)
        dates = sorted(df['date'].unique())
        gaps = []
        for i in range(len(dates) - 1):
            gap_days = (dates[i + 1] - dates[i]).days
            if gap_days > 7:  # More than a week
                gaps.append({
                    'from': str(dates[i]),
                    'to': str(dates[i + 1]),
                    'days': gap_days
                })
        
        results['checks']['date_gaps'] = {
            'pass': len(gaps) == 0,
            'gaps': gaps if gaps else None
        }
        
        if len(gaps) > 5:
            results['status'] = 'WARN'
        
        # Check 10: Expiry distribution
        expiries = df['expiry'].unique()
        results['checks']['expiry_distribution'] = {
            'unique_expiries': len(expiries),
            'expiries_per_day': round(len(expiries) / df['date'].nunique(), 2)
        }
        
        return results
    
    def validate_multiple(self, underlyings: list) -> dict:
        """Validate multiple underlyings"""
        logger.info(f"Validating {len(underlyings)} underlyings")
        
        all_results = {}
        
        for underlying in underlyings:
            result = self.validate_underlying(underlying)
            all_results[underlying] = result
        
        # Generate summary
        summary = {
            'total': len(underlyings),
            'pass': sum(1 for r in all_results.values() if r['status'] == 'PASS'),
            'warn': sum(1 for r in all_results.values() if r['status'] == 'WARN'),
            'fail': sum(1 for r in all_results.values() if r['status'] == 'FAIL'),
            'missing': sum(1 for r in all_results.values() if r['status'] == 'MISSING'),
            'error': sum(1 for r in all_results.values() if r['status'] == 'ERROR')
        }
        
        return {
            'summary': summary,
            'results': all_results
        }
    
    def print_report(self, results: dict):
        """Print validation report"""
        if 'summary' in results:
            # Multiple underlyings
            self._print_summary_report(results)
        else:
            # Single underlying
            self._print_single_report(results)
    
    def _print_single_report(self, result: dict):
        """Print report for single underlying"""
        print("\n" + "=" * 80)
        print(f"VALIDATION REPORT: {result['underlying']}")
        print("=" * 80)
        
        print(f"\nStatus: {result['status']}")
        
        if result['status'] in ['MISSING', 'ERROR']:
            print(f"Error: {result.get('error')}")
            return
        
        print(f"Total Records: {result['total_records']:,}")
        
        print("\nChecks:")
        print("-" * 80)
        
        for check_name, check_result in result['checks'].items():
            status = "✓" if check_result.get('pass', True) else "✗"
            print(f"\n{status} {check_name.replace('_', ' ').title()}")
            
            for key, value in check_result.items():
                if key != 'pass' and value is not None:
                    print(f"    {key}: {value}")
        
        print("\n" + "=" * 80)
    
    def _print_summary_report(self, results: dict):
        """Print summary report for multiple underlyings"""
        summary = results['summary']
        
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal Underlyings: {summary['total']}")
        print(f"  ✓ Pass: {summary['pass']}")
        print(f"  ⚠ Warn: {summary['warn']}")
        print(f"  ✗ Fail: {summary['fail']}")
        print(f"  ? Missing: {summary['missing']}")
        print(f"  ! Error: {summary['error']}")
        
        print("\nDetails:")
        print("-" * 80)
        
        for underlying, result in sorted(results['results'].items()):
            status_icon = {
                'PASS': '✓',
                'WARN': '⚠',
                'FAIL': '✗',
                'MISSING': '?',
                'ERROR': '!'
            }.get(result['status'], '?')
            
            records = result.get('total_records', 0)
            print(f"{status_icon} {underlying:20} {result['status']:8} {records:10,} records")
        
        print("\n" + "=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Validate historical option chain data'
    )
    
    parser.add_argument('--underlying', default='ALL_INDICES',
                       help='Underlying to validate (ALL_INDICES, ALL_STOCKS, '
                            'TOP_LIQUID_STOCKS, or specific symbol)')
    
    args = parser.parse_args()
    
    validator = HistoricalDataValidator()
    
    # Determine underlyings
    underlyings = []
    
    if args.underlying == 'ALL_INDICES':
        underlyings = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
    
    elif args.underlying == 'ALL_STOCKS':
        underlyings = validator.stock_loader.get_all_symbols()
    
    elif args.underlying == 'TOP_LIQUID_STOCKS':
        underlyings = ['ITC', 'ONGC', 'SBIN', 'NATIONALUM', 'TCS', 'GAIL', 'HINDZINC', 'VEDL',
                      'CANBK', 'LICI', 'TATASTEEL', 'COALINDIA', 'HDFCBANK', 'SAIL', 'WIPRO',
                      'BANKINDIA', 'PIIND', 'RELIANCE', 'SUNPHARMA', 'TIINDIA']
    
    else:
        underlyings = [args.underlying]
    
    # Validate
    if len(underlyings) == 1:
        result = validator.validate_underlying(underlyings[0])
        validator.print_report(result)
    else:
        results = validator.validate_multiple(underlyings)
        validator.print_report(results)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
