"""
Dry Run Script for Options Trading System

Runs the complete system with real Upstox API data but WITHOUT executing trades.
Monitors and validates:
- Regime detection accuracy
- Strategy generation quality
- Signal frequency (~2 trades/week max)
- Kill switch behavior
- All eligibility rules

Logs all decisions for 1-2 week validation period.
"""

import os
import sys
import logging
import time
from datetime import datetime, date, timedelta
from pathlib import Path
import pandas as pd
import pytz

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.options.config_loader import get_config
from src.options.upstox_adapter import UpstoxAdapter
from src.options.regime_detector import RegimeDetector, Regime
from src.options.strategy_generator import StrategyGenerator
from src.options.trade_eligibility_validator import TradeEligibilityValidator
from src.options.capital_scaling_engine import CapitalScalingEngine
from src.options.survival_rules_engine import (
    SurvivalRulesEngine, Position, Trade, PerformanceMetrics
)
from src.options.stock_options_loader import get_stock_loader

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/dry_run.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DryRunMonitor:
    """
    Dry run monitor for options trading system
    
    Runs complete signal generation pipeline with real data
    but does NOT execute trades. Logs all decisions for validation.
    """
    
    def __init__(self):
        """Initialize dry run monitor"""
        logger.info("=" * 80)
        logger.info("DRY RUN MODE - NO TRADES WILL BE EXECUTED")
        logger.info("=" * 80)
        
        # Load configuration
        self.config = get_config()
        
        # Set API credentials from environment
        self._set_api_credentials()
        
        # Initialize components
        self.upstox = UpstoxAdapter(self.config.upstox)
        self.regime_detector = RegimeDetector(self.config.regime_detection)
        self.strategy_generator = StrategyGenerator(self.config.strategies)
        self.eligibility_validator = TradeEligibilityValidator(self.config)
        self.capital_scaling = CapitalScalingEngine(self.config)
        self.survival_rules = SurvivalRulesEngine(
            self.config.survival_rules,
            self.config.capital.base_capital
        )
        
        # Load stock options mapping
        self.stock_loader = get_stock_loader()
        
        # Initialize capital scaling state
        self.scaling_state = self.capital_scaling.initialize_state(
            starting_capital=self.config.capital.base_capital,
            trading_start_date=datetime.now(IST)
        )
        
        # State tracking
        self.signals_generated = []
        self.signals_rejected = []
        self.regime_history = []
        self.iv_history = pd.Series(dtype=float)
        
        # Mock performance (for dry run)
        self.mock_performance = PerformanceMetrics(
            current_equity=self.config.capital.base_capital,
            ytd_gross_profits=0.0,
            ytd_tax_liability=0.0,
            cash_buffer=self.config.capital.base_capital * 0.3
        )
        
        # Create output directory
        self.output_dir = Path('data/dry_run')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Dry run initialized with base capital: ₹{self.config.capital.base_capital:,.0f}")
    
    def _set_api_credentials(self):
        """Set Upstox API credentials from environment or user input"""
        # Check if credentials are in environment
        api_key = os.getenv('UPSTOX_API_KEY', '').strip()
        api_secret = os.getenv('UPSTOX_API_SECRET', '').strip()
        access_token = os.getenv('UPSTOX_ACCESS_TOKEN', '').strip()

        if not access_token:
            raise RuntimeError("UPSTOX_ACCESS_TOKEN missing. Export it before running dry run.")

        if api_key:
            self.config.upstox.api_key = api_key
        if api_secret:
            self.config.upstox.api_secret = api_secret
        self.config.upstox.access_token = access_token
        logger.info("Using Upstox credentials from environment variables")
    
    def run_single_cycle(self, underlying: str = 'NIFTY') -> dict:
        """
        Run single monitoring cycle
        
        Args:
            underlying: Underlying to monitor ('NIFTY' or 'BANKNIFTY')
        
        Returns:
            dict: Cycle results
        """
        current_time = datetime.now(IST)
        logger.info(f"\n{'=' * 80}")
        logger.info(f"DRY RUN CYCLE - {current_time.strftime('%Y-%m-%d %H:%M:%S IST')}")
        logger.info(f"Underlying: {underlying}")
        logger.info(f"{'=' * 80}\n")
        
        results = {
            'timestamp': current_time,
            'underlying': underlying,
            'regime': None,
            'strategy': None,
            'eligibility': None,
            'kill_switches': None,
            'signal_generated': False,
            'rejection_reasons': []
        }
        
        try:
            # Step 1: Fetch option chain
            logger.info("Step 1: Fetching option chain from Upstox...")
            expiry = self._get_next_expiry(underlying)
            
            # Check if it's a stock and get instrument key
            stock_info = self.stock_loader.get_stock(underlying)
            instrument_key = stock_info.instrument_key if stock_info else None
            
            try:
                option_chain = self.upstox.fetch_option_chain(underlying, expiry, instrument_key=instrument_key)
            except Exception as e:
                logger.error(f"Failed to fetch option chain: {e}")
                results['rejection_reasons'].append(f"API error: {str(e)}")
                return results
            
            if option_chain.empty:
                logger.warning("Empty option chain received - market may be closed or no data for this expiry")
                logger.info("This is normal if:")
                logger.info("  - Market is closed (trading hours: 9:15 AM - 3:30 PM IST)")
                logger.info("  - Expiry date has no options listed yet")
                logger.info("  - It's a holiday")
                results['rejection_reasons'].append("Empty option chain")
                return results
            
            logger.info(f"Fetched {len(option_chain)} option contracts")
            
            # Step 2: Update IV history
            logger.info("\nStep 2: Updating IV history...")
            atm_iv = self._get_atm_iv(option_chain)
            self.iv_history = pd.concat([
                self.iv_history,
                pd.Series([atm_iv], index=[current_time])
            ])
            logger.info(f"Current ATM IV: {atm_iv:.4f}")
            
            # Step 3: Detect regime
            logger.info("\nStep 3: Detecting market regime...")
            regime_state = self.regime_detector.detect_regime(
                option_chain,
                self.iv_history,
                underlying_regime="NORMAL"  # Mock - would come from Northstar v3
            )
            
            results['regime'] = {
                'regime': regime_state.regime.value,
                'confidence': regime_state.confidence,
                'reason': regime_state.reason,
                'iv_rank': regime_state.metrics.iv_rank,
                'iv_trend': regime_state.metrics.iv_trend,
                'vol_of_vol_elevated': regime_state.metrics.vol_of_vol_elevated,
                'days_in_regime': regime_state.metrics.days_in_regime
            }
            
            self.regime_history.append(results['regime'])
            
            logger.info(f"Regime: {regime_state.regime.value}")
            logger.info(f"Confidence: {regime_state.confidence:.2%}")
            logger.info(f"IV Rank: {regime_state.metrics.iv_rank:.2%}")
            logger.info(f"Days in regime: {regime_state.metrics.days_in_regime}")
            
            # Check regime persistence
            if not self.regime_detector.check_regime_persistence(regime_state.regime):
                reason = f"Regime not persistent (need {self.config.regime_detection.regime_persistence_days} days)"
                logger.info(f"❌ {reason}")
                results['rejection_reasons'].append(reason)
                return results
            
            # Step 4: Generate strategy
            logger.info("\nStep 4: Generating strategy...")
            strategy = self.strategy_generator.generate_strategy(
                regime_state.regime,
                option_chain,
                underlying
            )
            
            if strategy is None:
                reason = f"No strategy for regime {regime_state.regime.value}"
                logger.info(f"❌ {reason}")
                results['rejection_reasons'].append(reason)
                return results
            
            if not strategy.is_valid:
                reason = f"Invalid strategy: {strategy.validation_errors}"
                logger.warning(f"❌ {reason}")
                results['rejection_reasons'].append(reason)
                return results
            
            results['strategy'] = {
                'type': strategy.strategy_type.value,
                'max_loss': strategy.max_loss,
                'max_profit': strategy.max_profit,
                'net_credit_debit': strategy.net_credit_debit,
                'risk_reward_ratio': strategy.risk_reward_ratio,
                'portfolio_greeks': {
                    'delta': strategy.portfolio_greeks.delta,
                    'gamma': strategy.portfolio_greeks.gamma,
                    'theta': strategy.portfolio_greeks.theta,
                    'vega': strategy.portfolio_greeks.vega
                },
                'days_to_expiry': strategy.days_to_expiry
            }
            
            logger.info(f"Strategy: {strategy.strategy_type.value}")
            logger.info(f"Max Loss: ₹{strategy.max_loss:,.0f}")
            logger.info(f"Max Profit: ₹{strategy.max_profit:,.0f}")
            logger.info(f"Net Credit/Debit: ₹{strategy.net_credit_debit:,.0f}")
            
            # Step 5: Check eligibility
            logger.info("\nStep 5: Checking trade eligibility...")
            eligibility = self.eligibility_validator.validate_trade(
                strategy,
                option_chain,
                regime_state,
                current_time
            )
            
            results['eligibility'] = {
                'is_eligible': eligibility.is_eligible,
                'passed_checks': eligibility.passed_checks,
                'failed_checks': eligibility.failed_checks,
                'warnings': eligibility.warnings
            }
            
            if not eligibility.is_eligible:
                logger.warning(f"❌ Trade not eligible:")
                for check in eligibility.failed_checks:
                    logger.warning(f"  - {check}")
                results['rejection_reasons'].extend(eligibility.failed_checks)
                return results
            
            logger.info("✓ Trade eligible")
            for check in eligibility.passed_checks:
                logger.info(f"  ✓ {check}")
            
            # Step 6: Check survival rules
            logger.info("\nStep 6: Checking survival rules (kill switches)...")
            
            # Create mock position for proposed trade
            proposed_position = Position(
                position_id=f"DRY_RUN_{current_time.timestamp()}",
                strategy_type=strategy.strategy_type.value,
                max_loss=strategy.max_loss,
                entry_time=current_time,
                is_short_vol=strategy.strategy_type.value in ['iron_condor', 'calendar_spread']
            )
            
            kill_switch_status = self.survival_rules.check_all_kill_switches(
                open_positions=[],  # No open positions in dry run
                closed_trades=[],   # No closed trades yet
                performance=self.mock_performance,
                current_time=current_time,
                proposed_trade=proposed_position
            )
            
            results['kill_switches'] = {
                'active': kill_switch_status.active,
                'triggered_rules': kill_switch_status.triggered_rules,
                'reason': kill_switch_status.reason,
                'cooldown_until': kill_switch_status.cooldown_until.isoformat() if kill_switch_status.cooldown_until else None
            }
            
            if kill_switch_status.active:
                logger.warning(f"❌ Kill switches active:")
                logger.warning(f"  Triggered: {kill_switch_status.triggered_rules}")
                logger.warning(f"  Reason: {kill_switch_status.reason}")
                results['rejection_reasons'].append(f"Kill switch: {kill_switch_status.reason}")
                return results
            
            logger.info("✓ All kill switches passed")
            
            # Step 7: Calculate position size
            logger.info("\nStep 7: Calculating position size...")
            position_size = self.capital_scaling.get_position_size(
                self.scaling_state,
                strategy.max_loss
            )
            
            logger.info(f"Current risk per trade: {self.scaling_state.current_risk_pct:.2%}")
            logger.info(f"Position size: {position_size} lots")
            logger.info(f"Capital at risk: ₹{strategy.max_loss * position_size:,.0f}")
            
            # SUCCESS - Signal generated
            logger.info("\n" + "=" * 80)
            logger.info("✅ TRADE SIGNAL GENERATED (DRY RUN - NOT EXECUTED)")
            logger.info("=" * 80)
            
            results['signal_generated'] = True
            results['position_size'] = position_size
            results['capital_at_risk'] = strategy.max_loss * position_size
            
            self.signals_generated.append(results)
            
            # Log signal details
            self._log_signal(results)
            
        except Exception as e:
            logger.error(f"Error in dry run cycle: {e}", exc_info=True)
            results['rejection_reasons'].append(f"Error: {str(e)}")
        
        return results
    
    def run_continuous(
        self,
        duration_days: int = 14,
        check_interval_minutes: int = 60,
        underlyings: list = None
    ):
        """
        Run continuous monitoring for specified duration
        
        Args:
            duration_days: Number of days to monitor (default: 14)
            check_interval_minutes: Minutes between checks (default: 60)
            underlyings: List of underlyings to monitor (default: ['NIFTY', 'BANKNIFTY'])
        """
        if underlyings is None:
            underlyings = ['NIFTY', 'BANKNIFTY']
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"STARTING CONTINUOUS DRY RUN")
        logger.info(f"Duration: {duration_days} days")
        logger.info(f"Check interval: {check_interval_minutes} minutes")
        logger.info(f"Underlyings: {underlyings}")
        logger.info(f"{'=' * 80}\n")
        
        start_time = datetime.now(IST)
        end_time = start_time + timedelta(days=duration_days)
        
        cycle_count = 0
        
        try:
            while datetime.now(IST) < end_time:
                cycle_count += 1
                
                # Run cycle for each underlying
                for underlying in underlyings:
                    try:
                        results = self.run_single_cycle(underlying)
                        
                        # Save results
                        self._save_cycle_results(results)
                        
                    except Exception as e:
                        logger.error(f"Error in cycle for {underlying}: {e}", exc_info=True)
                
                # Generate daily summary
                if cycle_count % 24 == 0:  # Every 24 hours (if hourly checks)
                    self._generate_daily_summary()
                
                # Wait for next cycle
                logger.info(f"\nWaiting {check_interval_minutes} minutes until next check...")
                time.sleep(check_interval_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("\n\nDry run interrupted by user")
        
        finally:
            # Generate final report
            self._generate_final_report()
    
    def _get_next_expiry(self, underlying: str = 'NIFTY') -> date:
        """
        Get next available weekly expiry from Upstox for specific underlying
        
        Fetches actual expiries from API instead of calculating,
        since NIFTY and BANKNIFTY may have different expiry schedules.
        
        Args:
            underlying: Underlying symbol (index or stock)
        
        Returns:
            Next available expiry date
        """
        try:
            # Check if it's a stock or index
            stock_info = self.stock_loader.get_stock(underlying)
            
            if stock_info:
                # Stock option - use ISIN-based instrument key
                instrument_key = stock_info.instrument_key
                logger.debug(f"Using stock instrument key: {instrument_key}")
            else:
                # Index option - get from adapter's mapping
                instrument_key = self.upstox.instrument_key_map.get(underlying)
                if not instrument_key:
                    raise ValueError(f"Unknown underlying: {underlying}")
                logger.debug(f"Using index instrument key: {instrument_key}")
            
            # Fetch available option contracts
            url = self.config.upstox.endpoints.get('option_contracts', 'https://api.upstox.com/v2/option/contract')
            params = {'instrument_key': instrument_key}
            
            response = self.upstox._make_request('GET', url, params=params)
            
            if response.get('status') == 'success' and response.get('data'):
                # Extract unique expiries
                expiries = set()
                for contract in response['data']:
                    if 'expiry' in contract:
                        expiry_str = contract['expiry']
                        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                        expiries.add(expiry_date)
                
                if expiries:
                    # Get nearest future expiry
                    today = date.today()
                    future_expiries = [e for e in expiries if e > today]
                    
                    if future_expiries:
                        next_expiry = min(future_expiries)
                        logger.info(f"Found next expiry for {underlying} from API: {next_expiry}")
                        return next_expiry
        
        except Exception as e:
            logger.warning(f"Could not fetch expiries from API for {underlying}: {e}")
        
        # Fallback: calculate next Thursday
        today = date.today()
        days_until_thursday = (3 - today.weekday()) % 7
        if days_until_thursday == 0:
            days_until_thursday = 7  # Next Thursday
        next_expiry = today + timedelta(days=days_until_thursday)
        
        logger.info(f"Using calculated expiry (fallback) for {underlying}: {next_expiry}")
        return next_expiry
    
    def _get_atm_iv(self, option_chain: pd.DataFrame) -> float:
        """Get ATM implied volatility"""
        spot = option_chain['underlying_price'].iloc[0]
        option_chain['distance_to_atm'] = abs(option_chain['strike'] - spot)
        atm_strike = option_chain.loc[option_chain['distance_to_atm'].idxmin(), 'strike']
        atm_options = option_chain[option_chain['strike'] == atm_strike]
        return atm_options['iv'].mean()
    
    def _log_signal(self, results: dict):
        """Log signal details to file"""
        signal_file = self.output_dir / 'signals.log'
        
        with open(signal_file, 'a') as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"SIGNAL GENERATED: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S IST')}\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"Underlying: {results['underlying']}\n")
            f.write(f"Regime: {results['regime']['regime']} (confidence: {results['regime']['confidence']:.2%})\n")
            f.write(f"Strategy: {results['strategy']['type']}\n")
            f.write(f"Max Loss: ₹{results['strategy']['max_loss']:,.0f}\n")
            f.write(f"Max Profit: ₹{results['strategy']['max_profit']:,.0f}\n")
            f.write(f"Position Size: {results.get('position_size', 0)} lots\n")
            f.write(f"Capital at Risk: ₹{results.get('capital_at_risk', 0):,.0f}\n")
            f.write(f"\n")
    
    def _save_cycle_results(self, results: dict):
        """Save cycle results to CSV"""
        results_file = self.output_dir / 'cycle_results.csv'
        
        # Flatten results for CSV
        flat_results = {
            'timestamp': results['timestamp'],
            'underlying': results['underlying'],
            'signal_generated': results['signal_generated'],
            'regime': results['regime']['regime'] if results['regime'] else None,
            'regime_confidence': results['regime']['confidence'] if results['regime'] else None,
            'iv_rank': results['regime']['iv_rank'] if results['regime'] else None,
            'strategy_type': results['strategy']['type'] if results['strategy'] else None,
            'max_loss': results['strategy']['max_loss'] if results['strategy'] else None,
            'max_profit': results['strategy']['max_profit'] if results['strategy'] else None,
            'rejection_reasons': '; '.join(results['rejection_reasons'])
        }
        
        df = pd.DataFrame([flat_results])
        
        if results_file.exists():
            df.to_csv(results_file, mode='a', header=False, index=False)
        else:
            df.to_csv(results_file, index=False)
    
    def _generate_daily_summary(self):
        """Generate daily summary report"""
        logger.info("\n" + "=" * 80)
        logger.info("DAILY SUMMARY")
        logger.info("=" * 80)
        
        # Load results
        results_file = self.output_dir / 'cycle_results.csv'
        if not results_file.exists():
            logger.info("No results yet")
            return
        
        df = pd.read_csv(results_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Last 24 hours
        last_24h = df[df['timestamp'] > datetime.now(IST) - timedelta(hours=24)]
        
        logger.info(f"Cycles run: {len(last_24h)}")
        logger.info(f"Signals generated: {last_24h['signal_generated'].sum()}")
        logger.info(f"Signal rate: {last_24h['signal_generated'].mean():.1%}")
        
        if len(last_24h) > 0:
            logger.info(f"\nRegime distribution:")
            regime_counts = last_24h['regime'].value_counts()
            for regime, count in regime_counts.items():
                logger.info(f"  {regime}: {count} ({count/len(last_24h):.1%})")
        
        logger.info("=" * 80 + "\n")
    
    def _generate_final_report(self):
        """Generate final validation report"""
        logger.info("\n" + "=" * 80)
        logger.info("FINAL DRY RUN REPORT")
        logger.info("=" * 80)
        
        # Load all results
        results_file = self.output_dir / 'cycle_results.csv'
        if not results_file.exists():
            logger.info("No results to report")
            return
        
        df = pd.read_csv(results_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Overall statistics
        total_cycles = len(df)
        total_signals = df['signal_generated'].sum()
        signal_rate = total_signals / total_cycles if total_cycles > 0 else 0
        
        logger.info(f"\nOverall Statistics:")
        logger.info(f"  Total cycles: {total_cycles}")
        logger.info(f"  Signals generated: {total_signals}")
        logger.info(f"  Signal rate: {signal_rate:.1%}")
        logger.info(f"  Duration: {(df['timestamp'].max() - df['timestamp'].min()).days} days")
        
        # Weekly signal rate
        signals_per_week = total_signals / ((df['timestamp'].max() - df['timestamp'].min()).days / 7)
        logger.info(f"  Signals per week: {signals_per_week:.1f}")
        
        # Regime distribution
        logger.info(f"\nRegime Distribution:")
        regime_counts = df['regime'].value_counts()
        for regime, count in regime_counts.items():
            logger.info(f"  {regime}: {count} ({count/total_cycles:.1%})")
        
        # Strategy distribution
        logger.info(f"\nStrategy Distribution:")
        strategy_counts = df[df['signal_generated']]['strategy_type'].value_counts()
        for strategy, count in strategy_counts.items():
            logger.info(f"  {strategy}: {count} ({count/total_signals:.1%})")
        
        # Rejection reasons
        logger.info(f"\nTop Rejection Reasons:")
        all_rejections = []
        for reasons in df['rejection_reasons'].dropna():
            if reasons:
                all_rejections.extend(reasons.split('; '))
        
        if all_rejections:
            rejection_counts = pd.Series(all_rejections).value_counts().head(10)
            for reason, count in rejection_counts.items():
                logger.info(f"  {reason}: {count}")
        
        # Validation checks
        logger.info(f"\nValidation Checks:")
        logger.info(f"  ✓ Signal frequency: {signals_per_week:.1f}/week (target: ~2/week)")
        
        if signals_per_week <= 2.5:
            logger.info(f"    ✅ PASS - Signal frequency within target")
        else:
            logger.warning(f"    ⚠️  WARNING - Signal frequency above target")
        
        logger.info("=" * 80)
        
        # Save report
        report_file = self.output_dir / 'final_report.txt'
        with open(report_file, 'w') as f:
            f.write("DRY RUN VALIDATION REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total cycles: {total_cycles}\n")
            f.write(f"Signals generated: {total_signals}\n")
            f.write(f"Signal rate: {signal_rate:.1%}\n")
            f.write(f"Signals per week: {signals_per_week:.1f}\n")
            f.write(f"\nValidation: {'PASS' if signals_per_week <= 2.5 else 'FAIL'}\n")
        
        logger.info(f"\nReport saved to: {report_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Dry run options trading system')
    parser.add_argument('--mode', choices=['single', 'continuous'], default='single',
                       help='Run mode: single cycle or continuous monitoring')
    parser.add_argument('--duration', type=int, default=14,
                       help='Duration in days for continuous mode (default: 14)')
    parser.add_argument('--interval', type=int, default=60,
                       help='Check interval in minutes for continuous mode (default: 60)')
    parser.add_argument('--underlying', 
                       default='ALL_INDICES',
                       help='Underlying to monitor. Options: '
                            'ALL_INDICES (default), '
                            'ALL_STOCKS, '
                            'TOP_LIQUID_STOCKS (top 20), '
                            'RECOMMENDED_STOCKS (beginner-friendly), '
                            'specific index (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY), '
                            'specific stock symbol (e.g., RELIANCE, TCS), '
                            'or sector name (e.g., Banking, IT)')
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = DryRunMonitor()
    
    # Determine underlyings based on argument
    underlyings = []
    
    if args.underlying == 'ALL_INDICES':
        underlyings = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
        logger.info(f"Monitoring all 4 indices")
    
    elif args.underlying == 'ALL_STOCKS':
        underlyings = monitor.stock_loader.get_all_symbols()
        logger.info(f"Monitoring all {len(underlyings)} stocks with options")
    
    elif args.underlying == 'TOP_LIQUID_STOCKS':
        # Top 20 most liquid stocks
        top_stocks = ['ITC', 'ONGC', 'SBIN', 'NATIONALUM', 'TCS', 'GAIL', 'HINDZINC', 'VEDL', 
                     'CANBK', 'LICI', 'TATASTEEL', 'COALINDIA', 'HDFCBANK', 'SAIL', 'WIPRO',
                     'BANKINDIA', 'PIIND', 'RELIANCE', 'SUNPHARMA', 'TIINDIA']
        underlyings = top_stocks
        logger.info(f"Monitoring top 20 liquid stocks")
    
    elif args.underlying == 'RECOMMENDED_STOCKS':
        recommended = monitor.stock_loader.get_recommended_for_beginners()
        underlyings = [stock.symbol for stock in recommended]
        logger.info(f"Monitoring {len(underlyings)} recommended stocks")
    
    elif args.underlying in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']:
        # Single index
        underlyings = [args.underlying]
        logger.info(f"Monitoring single index: {args.underlying}")
    
    elif monitor.stock_loader.get_stock(args.underlying):
        # Single stock
        underlyings = [args.underlying]
        stock_info = monitor.stock_loader.get_stock(args.underlying)
        logger.info(f"Monitoring single stock: {stock_info.display_name}")
    
    else:
        # Try as sector name
        sector_stocks = monitor.stock_loader.get_by_sector(args.underlying)
        if sector_stocks:
            underlyings = [stock.symbol for stock in sector_stocks]
            logger.info(f"Monitoring {len(underlyings)} stocks in {args.underlying} sector")
        else:
            logger.error(f"Unknown underlying or sector: {args.underlying}")
            logger.info(f"Available indices: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY")
            logger.info(f"Available sectors: {', '.join(monitor.stock_loader.get_sectors())}")
            logger.info(f"Use --underlying ALL_STOCKS to see all available stocks")
            return
    
    # Run based on mode
    if args.mode == 'single':
        logger.info("Running single cycle...")
        for underlying in underlyings:
            monitor.run_single_cycle(underlying)
    else:
        logger.info("Running continuous monitoring...")
        monitor.run_continuous(
            duration_days=args.duration,
            check_interval_minutes=args.interval,
            underlyings=underlyings
        )


if __name__ == '__main__':
    main()
