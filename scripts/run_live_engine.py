#!/usr/bin/env python3
"""
Live Engine Runner - Real-Time Integration

Continuously runs the engine with live market data from Upstox.
Updates state snapshots for dashboard consumption.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import json
import logging
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env.options
load_dotenv('.env.options')

from src.volatility.market_data_feed import MarketDataFeed
from src.volatility.state_engine import VolatilityStateEngine
from src.volatility.regime_detector import RegimeDetector
from src.volatility.greeks_aggregator import GreeksAggregator
from src.volatility.risk_authority import UnifiedRiskAuthority
from src.volatility.strategy_generator import StrategyGenerator
from src.volatility.capital_allocator import CapitalAllocator
from src.volatility.performance_monitor import PerformanceMonitor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_engine.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LiveEngineRunner:
    """Runs the engine continuously with live market data"""
    
    def __init__(self, update_interval: int = 30):
        """
        Initialize live engine runner
        
        Args:
            update_interval: Seconds between updates (default 30)
        """
        self.update_interval = update_interval
        self.running = False
        self.ist_tz = ZoneInfo("Asia/Kolkata")
        
        # Create necessary directories
        os.makedirs("logs", exist_ok=True)
        os.makedirs("snapshots", exist_ok=True)
        
        logger.info("Initializing live engine components...")
        
        # Get Upstox credentials from environment
        access_token = os.getenv('UPSTOX_ACCESS_TOKEN')
        if not access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN not found in environment. Check .env.options file.")
        
        # Initialize market data feed
        self.market_feed = MarketDataFeed(access_token=access_token)
        
        # Initialize core components
        self.state_engine = VolatilityStateEngine()
        self.regime_detector = RegimeDetector()
        self.greeks_aggregator = GreeksAggregator()
        self.risk_authority = UnifiedRiskAuthority()  # Uses default config/risk.yaml
        self.strategy_generator = StrategyGenerator()  # No parameters needed
        self.capital_allocator = CapitalAllocator()  # Uses default strategy buckets
        self.performance_monitor = PerformanceMonitor()  # Uses default history size
        
        # State tracking
        self.current_state = None
        self.cycle_count = 0
        self.last_regime = None
        
        logger.info("✅ Live engine initialized")

    def _now_ist(self) -> datetime:
        """Return current timestamp in Asia/Kolkata."""
        return datetime.now(self.ist_tz)
    
    def is_market_hours(self) -> bool:
        """Check if currently in NSE market hours (09:15-15:30 IST, Mon-Fri)."""
        now = self._now_ist()
        market_start = dt_time(9, 15)
        market_end = dt_time(15, 30)
        
        # Check if weekday
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        current_time = now.time()
        return market_start <= current_time <= market_end
    
    def fetch_live_market_data(self) -> Dict[str, Any]:
        """Fetch live market data from Upstox"""
        try:
            logger.info("Fetching live market data...")
            
            market_data = {}
            
            # Fetch index prices
            indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
            for index in indices:
                try:
                    price = self.market_feed.get_underlying_price(index)
                    market_data[f'{index}_price'] = price
                    logger.info(f"  {index}: ₹{price:,.2f}")
                except Exception as e:
                    logger.warning(f"  Failed to fetch {index}: {e}")
                    market_data[f'{index}_price'] = None
            
            # Fetch option chain for NIFTY (primary index)
            try:
                expiries = self.market_feed.get_next_expiries('NIFTY', num_expiries=1)
                if expiries:
                    option_chain = self.market_feed.get_option_chain('NIFTY', expiries[0])
                    market_data['option_chain'] = option_chain
                    chain_len = len(option_chain) if hasattr(option_chain, '__len__') else 0
                    logger.info(f"  Option chain: {chain_len} contracts")
                else:
                    logger.warning("  No expiries available")
                    market_data['option_chain'] = None
            except Exception as e:
                logger.warning(f"  Failed to fetch option chain: {e}")
                market_data['option_chain'] = None
            
            # Mock additional data (replace with real calculations later)
            market_data['vix_level'] = 15.5  # Mock VIX
            market_data['realized_vol'] = 0.18  # Mock realized vol
            market_data['vol_of_vol'] = 0.05  # Mock vol of vol
            market_data['implied_corr'] = 0.45  # Mock correlation
            market_data['realized_corr'] = 0.42
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}", exc_info=True)
            return {}
    
    def update_state(self, market_data: Dict[str, Any]):
        """Update volatility state with new market data"""
        try:
            logger.info("Updating volatility state...")
            
            # Update IV surface if we have option chain
            option_chain = market_data.get('option_chain')
            if option_chain is not None and not (hasattr(option_chain, 'empty') and option_chain.empty):
                self.state_engine.update_iv_surface(option_chain)
            
            # Update volatility metrics
            if 'vix_level' in market_data:
                self.state_engine.update_volatility_metrics(
                    vix_level=market_data.get('vix_level'),
                    realized_vol_20d=market_data.get('realized_vol'),
                    vol_of_vol=market_data.get('vol_of_vol')
                )
            
            # Update correlations
            if 'implied_corr' in market_data:
                # Mock correlation matrix (replace with real calculation)
                correlation_matrix = {
                    ('NIFTY', 'BANKNIFTY'): 0.85,
                    ('NIFTY', 'FINNIFTY'): 0.75,
                    ('BANKNIFTY', 'FINNIFTY'): 0.70
                }
                self.state_engine.update_correlations(
                    correlation_matrix,
                    market_data.get('implied_corr', 0.5),
                    market_data.get('realized_corr', 0.5)
                )
            
            # Get updated state
            self.current_state = self.state_engine.get_state()
            
            logger.info("✅ State updated")
            
        except Exception as e:
            logger.error(f"Error updating state: {e}", exc_info=True)
    
    def detect_regime(self):
        """Detect current market regime"""
        try:
            if not self.current_state:
                return
            
            logger.info("Detecting market regime...")
            
            # For now, skip regime detection as it requires historical data
            # Set a default regime
            from src.volatility.regime_detector import VolatilityRegime
            regime = VolatilityRegime.TRANSITION
            
            self.current_state.regime = regime
            
            # Check for regime change
            if self.last_regime and self.last_regime != regime:
                logger.warning(f"🔄 Regime change: {self.last_regime} → {regime}")
            
            self.last_regime = regime
            logger.info(f"  Current regime: {regime.value}")
            
        except Exception as e:
            logger.error(f"Error detecting regime: {e}", exc_info=True)
    
    def compute_portfolio_greeks(self) -> Dict[str, float]:
        """Compute current portfolio Greeks"""
        try:
            if not self.current_state:
                return {}
            
            logger.info("Computing portfolio Greeks...")
            
            # For now, return mock Greeks since we don't have positions yet
            # In production, you would pass actual positions list
            greeks = {
                'delta': 0.0,
                'gamma': 0.0,
                'vega': 0.0,
                'theta': 0.0,
                'rho': 0.0
            }
            
            logger.info(f"  Delta: {greeks['delta']:.2f}, Gamma: {greeks['gamma']:.3f}, "
                       f"Vega: {greeks['vega']:.2f}, Theta: {greeks['theta']:.2f}")
            
            return greeks
            
        except Exception as e:
            logger.error(f"Error computing Greeks: {e}", exc_info=True)
            return {}
    
    def save_snapshot(self, market_data: Dict[str, Any], greeks: Dict[str, float]):
        """Save current state snapshot for dashboard"""
        try:
            # Convert regime to string if it's an enum
            regime_str = 'transition'
            if self.current_state and hasattr(self.current_state, 'regime'):
                regime = self.current_state.regime
                if hasattr(regime, 'value'):
                    regime_str = regime.value
                else:
                    regime_str = str(regime)
            
            # Get option chain length safely
            option_chain = market_data.get('option_chain')
            option_contracts_count = 0
            if option_chain is not None:
                if hasattr(option_chain, '__len__'):
                    option_contracts_count = len(option_chain)
            
            snapshot = {
                'timestamp': self._now_ist().isoformat(),
                'cycle': self.cycle_count,
                'regime': regime_str,
                'market_data': {
                    'NIFTY_price': market_data.get('NIFTY_price'),
                    'BANKNIFTY_price': market_data.get('BANKNIFTY_price'),
                    'FINNIFTY_price': market_data.get('FINNIFTY_price'),
                    'vix_level': market_data.get('vix_level'),
                    'option_contracts': option_contracts_count
                },
                'portfolio_greeks': greeks,
                'total_pnl': 0,  # Mock - replace with real P&L tracking
                'realized_pnl': 0,
                'unrealized_pnl': 0,
                'today_pnl': 0,
                'positions': [],  # Mock - replace with real positions
                'performance_metrics': {
                    'sharpe_ratio': 0,
                    'sortino_ratio': 0,
                    'win_rate': 0,
                    'total_trades': 0
                },
                'risk_metrics': {
                    'var_95': 0,
                    'cvar_95': 0,
                    'max_drawdown': 0,
                    'current_drawdown': 0
                },
                'strategy_allocations': {
                    'Dispersion': 0.30,
                    'Gamma Scalping': 0.25,
                    'Short Vol': 0.20,
                    'Long Vol': 0.15,
                    'Relative Value': 0.10
                },
                'execution_metrics': {
                    'fill_rate': 0.95,
                    'avg_slippage': 0.008,
                    'total_orders': 0,
                    'rejected_orders': 0
                }
            }
            
            # Save to current state file (for dashboard)
            snapshot_file = Path("snapshots/current_state.json")
            with open(snapshot_file, 'w') as f:
                json.dump(snapshot, f, indent=2)
            
            # Also save timestamped snapshot
            timestamp_file = Path(f"snapshots/state_{self._now_ist().strftime('%Y%m%d_%H%M%S')}.json")
            with open(timestamp_file, 'w') as f:
                json.dump(snapshot, f, indent=2)
            
            logger.info(f"✅ Snapshot saved: {snapshot_file}")
            
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}", exc_info=True)
    
    def run_cycle(self):
        """Run one complete update cycle"""
        try:
            self.cycle_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"CYCLE {self.cycle_count} - {self._now_ist().strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logger.info(f"{'='*60}")
            
            # Check if market is open
            if not self.is_market_hours():
                logger.info("⏸️  Market closed - waiting...")
                return
            
            # 1. Fetch live market data
            market_data = self.fetch_live_market_data()
            if not market_data:
                logger.warning("No market data available")
                return
            
            # 2. Update state
            self.update_state(market_data)
            
            # 3. Detect regime
            self.detect_regime()
            
            # 4. Compute Greeks
            greeks = self.compute_portfolio_greeks()
            
            # 5. Save snapshot for dashboard
            self.save_snapshot(market_data, greeks)
            
            logger.info(f"✅ Cycle {self.cycle_count} complete")
            
        except Exception as e:
            logger.error(f"Error in cycle {self.cycle_count}: {e}", exc_info=True)
    
    def start(self):
        """Start the live engine"""
        logger.info("\n" + "="*60)
        logger.info("LIVE ENGINE STARTING")
        logger.info("="*60)
        logger.info(f"Update interval: {self.update_interval} seconds")
        logger.info("Market hours: 9:15 AM - 3:30 PM IST (Mon-Fri)")
        logger.info("="*60 + "\n")
        
        self.running = True
        
        # Save PID for monitoring
        pid_file = Path("engine.pid")
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"PID: {os.getpid()} (saved to {pid_file})")
        
        try:
            while self.running:
                self.run_cycle()
                
                # Wait for next cycle
                logger.info(f"⏳ Waiting {self.update_interval} seconds until next cycle...\n")
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.stop()
    
    def stop(self):
        """Stop the live engine"""
        logger.info("\n" + "="*60)
        logger.info("LIVE ENGINE STOPPING")
        logger.info("="*60)
        
        self.running = False
        
        # Remove PID file
        pid_file = Path("engine.pid")
        if pid_file.exists():
            pid_file.unlink()
            logger.info("PID file removed")
        
        logger.info("✅ Live engine stopped")
        logger.info("="*60 + "\n")


def main():
    """Main entry point"""
    import argparse
    import subprocess
    
    parser = argparse.ArgumentParser(description='Run live volatility engine with Upstox data')
    parser.add_argument('--interval', type=int, default=30,
                       help='Update interval in seconds (default: 30)')
    parser.add_argument('--legacy', action='store_true',
                       help='Run legacy mock volatility loop instead of integrated options paper engine')
    parser.add_argument('--underlyings', type=str, default='NIFTY,BANKNIFTY,FINNIFTY',
                       help='Comma-separated underlyings for integrated engine')
    args = parser.parse_args()

    if args.legacy:
        engine = LiveEngineRunner(update_interval=args.interval)
        engine.start()
        return

    logger.info("Delegating to integrated V3 options paper engine (recommended path)")
    cmd = [
        sys.executable,
        "scripts/run_integrated_options_paper_engine.py",
        "--mode",
        "continuous",
        "--interval-seconds",
        str(max(10, int(args.interval))),
        "--underlyings",
        args.underlyings,
        "--aggressive",
        "--no-start-fresh-today",  # Changed to use persistence by default
    ]
    subprocess.call(cmd, cwd=str(Path(__file__).resolve().parents[1]))


if __name__ == "__main__":
    main()
