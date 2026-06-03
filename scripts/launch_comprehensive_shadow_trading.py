#!/usr/bin/env python3
"""
Comprehensive Shadow Trading System Launcher

Launches and manages the complete shadow trading infrastructure:
1. Daily shadow trading execution
2. Performance tracking and reporting
3. Decision audit trail
4. Monthly report generation
5. Validation metrics collection

This script ensures the shadow trading system is operational and collecting
the data needed for production deployment validation.
"""

import sys
import os
import json
import logging
try:
    import schedule  # type: ignore
except Exception:
    schedule = None
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Import shadow trading components
from src.live.daily_shadow_trader import DailyShadowTrader
from src.live.shadow_trading_scheduler import ShadowTradingScheduler
from src.live.monthly_report_generator import MonthlyReportGenerator

# Import core system components (optional in manual mode).
try:
    from src.orchestrator.system_orchestrator import SystemOrchestrator
except Exception:
    SystemOrchestrator = None  # type: ignore


class ComprehensiveShadowTradingSystem:
    """Comprehensive shadow trading system with full validation tracking"""
    
    def __init__(self, initial_capital: float = 10000000):  # ₹1 Crore
        self.initial_capital = initial_capital
        self.logger = logging.getLogger(__name__)
        
        # Data directories
        self.base_dir = Path("data/live/shadow_trading")
        self.positions_dir = self.base_dir / "positions"
        self.pnl_dir = self.base_dir / "pnl"
        self.decisions_dir = self.base_dir / "decisions"
        self.reports_dir = self.base_dir / "reports"
        self.logs_dir = self.base_dir / "logs"
        
        # Create directories
        for directory in [self.positions_dir, self.pnl_dir, self.decisions_dir, 
                         self.reports_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.daily_trader = None
        self.scheduler = None
        self.report_generator = None
        self.system_orchestrator = None
        
        # State tracking
        self.trading_state_file = self.base_dir / "trading_state.json"
        self.trading_state = self._load_trading_state()
        
        # Performance tracking
        self.performance_metrics = {}
        self.validation_metrics = {}
        
    def _load_trading_state(self) -> Dict[str, Any]:
        """Load trading state from disk"""
        if self.trading_state_file.exists():
            try:
                with open(self.trading_state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load trading state: {e}")
        
        return {
            'system_active': False,
            'last_trading_date': None,
            'total_trading_days': 0,
            'cumulative_return': 0.0,
            'current_positions': {},
            'performance_history': []
        }
    
    def _save_trading_state(self) -> None:
        """Save trading state to disk"""
        try:
            with open(self.trading_state_file, 'w') as f:
                json.dump(self.trading_state, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save trading state: {e}")
    
    def initialize_system(self) -> bool:
        """Initialize all shadow trading components"""
        try:
            self.logger.info("Initializing comprehensive shadow trading system...")
            
            # Initialize core system orchestrator
            if SystemOrchestrator is not None:
                self.system_orchestrator = SystemOrchestrator()
            else:
                self.system_orchestrator = None
                self.logger.warning("SystemOrchestrator unavailable; continuing in shadow-only mode")
            
            # Initialize daily trader
            self.daily_trader = DailyShadowTrader(
                initial_capital=self.initial_capital,
                data_directory=str(self.base_dir)
            )
            
            # Initialize scheduler
            self.scheduler = ShadowTradingScheduler(
                trader=self.daily_trader,
                data_directory=str(self.base_dir)
            )
            
            # Initialize report generator
            self.report_generator = MonthlyReportGenerator(
                data_directory=str(self.base_dir)
            )
            
            self.logger.info("Shadow trading system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize shadow trading system: {e}")
            return False
    
    def run_daily_trading(self, trading_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Execute daily shadow trading"""
        if trading_date is None:
            trading_date = datetime.now(timezone.utc)
        
        date_str = trading_date.strftime("%Y-%m-%d")
        self.logger.info(f"Executing shadow trading for {date_str}")
        
        try:
            # Check if market is open (simplified check)
            if not self._is_market_day(trading_date):
                self.logger.info(f"Market closed on {date_str} - skipping trading")
                return {'status': 'market_closed', 'date': date_str}
            
            # Execute daily trading
            trading_result = self.daily_trader.execute_daily_trading(trading_date)
            
            # Update trading state
            self.trading_state['last_trading_date'] = date_str
            if 'total_trading_days' not in self.trading_state:
                self.trading_state['total_trading_days'] = 0
            self.trading_state['total_trading_days'] += 1
            self.trading_state['system_active'] = True
            
            # Update performance tracking
            if 'daily_return' in trading_result:
                if 'cumulative_return' not in self.trading_state:
                    self.trading_state['cumulative_return'] = 0.0
                if 'performance_history' not in self.trading_state:
                    self.trading_state['performance_history'] = []
                    
                self.trading_state['cumulative_return'] += trading_result['daily_return']
                self.trading_state['performance_history'].append({
                    'date': date_str,
                    'daily_return': trading_result['daily_return'],
                    'cumulative_return': self.trading_state['cumulative_return']
                })
            
            # Update current positions
            if 'positions' in trading_result:
                self.trading_state['current_positions'] = trading_result['positions']
            
            # Save state
            self._save_trading_state()
            
            # Calculate validation metrics
            self._update_validation_metrics(trading_result)
            
            # Log trading result
            self._log_daily_trading_result(trading_date, trading_result)
            
            self.logger.info(f"Daily shadow trading completed for {date_str}")
            return trading_result
            
        except Exception as e:
            import traceback
            self.logger.error(f"Daily shadow trading failed for {date_str}: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {'status': 'error', 'date': date_str, 'error': str(e)}
    
    def _is_market_day(self, date: datetime) -> bool:
        """Check if given date is a market trading day"""
        # Simplified market day check (weekdays, excluding major holidays)
        if date.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Major Indian market holidays (simplified list)
        market_holidays_2026 = [
            '2026-01-26',  # Republic Day
            '2026-03-14',  # Holi
            '2026-08-15',  # Independence Day
            '2026-10-02',  # Gandhi Jayanti
            '2026-11-04',  # Diwali (approximate)
        ]
        
        date_str = date.strftime("%Y-%m-%d")
        return date_str not in market_holidays_2026
    
    def _update_validation_metrics(self, trading_result: Dict[str, Any]) -> None:
        """Update validation metrics for production deployment"""
        if not hasattr(self, 'validation_metrics') or self.validation_metrics is None:
            self.validation_metrics = {
                'total_returns': [],
                'daily_returns': [],
                'win_days': 0,
                'loss_days': 0,
                'max_drawdown': 0.0,
                'current_drawdown': 0.0,
                'peak_value': self.initial_capital
            }
        
        # Ensure all required keys exist
        if 'daily_returns' not in self.validation_metrics:
            self.validation_metrics['daily_returns'] = []
        if 'win_days' not in self.validation_metrics:
            self.validation_metrics['win_days'] = 0
        if 'loss_days' not in self.validation_metrics:
            self.validation_metrics['loss_days'] = 0
        if 'max_drawdown' not in self.validation_metrics:
            self.validation_metrics['max_drawdown'] = 0.0
        if 'current_drawdown' not in self.validation_metrics:
            self.validation_metrics['current_drawdown'] = 0.0
        if 'peak_value' not in self.validation_metrics:
            self.validation_metrics['peak_value'] = self.initial_capital
        
        # Update daily returns
        if 'daily_return' in trading_result:
            daily_return = trading_result['daily_return']
            self.validation_metrics['daily_returns'].append(daily_return)
            
            # Update win/loss counts
            if daily_return > 0:
                self.validation_metrics['win_days'] += 1
            elif daily_return < 0:
                self.validation_metrics['loss_days'] += 1
        
        # Update drawdown tracking
        current_value = self.initial_capital * (1 + self.trading_state.get('cumulative_return', 0.0))
        
        if current_value > self.validation_metrics['peak_value']:
            self.validation_metrics['peak_value'] = current_value
            self.validation_metrics['current_drawdown'] = 0.0
        else:
            if self.validation_metrics['peak_value'] > 0:
                drawdown = (self.validation_metrics['peak_value'] - current_value) / self.validation_metrics['peak_value']
                self.validation_metrics['current_drawdown'] = drawdown
                self.validation_metrics['max_drawdown'] = max(self.validation_metrics['max_drawdown'], drawdown)
    
    def _log_daily_trading_result(self, trading_date: datetime, result: Dict[str, Any]) -> None:
        """Log daily trading result to file"""
        date_str = trading_date.strftime("%Y-%m-%d")
        
        # Log to daily log file
        log_file = self.logs_dir / f"daily_trading_{trading_date.strftime('%Y%m')}.log"
        
        # Safely get validation metrics
        validation_metrics = getattr(self, 'validation_metrics', {})
        
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'trading_date': date_str,
            'result': result,
            'validation_metrics': validation_metrics
        }
        
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry, default=str) + '\n')
        except Exception as e:
            self.logger.error(f"Failed to log daily trading result: {e}")
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate validation report for production deployment"""
        # Initialize validation metrics if not present
        if not hasattr(self, 'validation_metrics') or not self.validation_metrics.get('daily_returns'):
            # Use trading state performance history if available
            if self.trading_state.get('performance_history'):
                daily_returns = [day['daily_return'] for day in self.trading_state['performance_history']]
                self.validation_metrics = {
                    'daily_returns': daily_returns,
                    'win_days': sum(1 for r in daily_returns if r > 0),
                    'loss_days': sum(1 for r in daily_returns if r < 0),
                    'max_drawdown': 0.0,
                    'current_drawdown': 0.0,
                    'peak_value': self.initial_capital
                }
            else:
                return {'error': 'No trading data available for validation'}
        
        daily_returns = np.array(self.validation_metrics['daily_returns'])
        
        # Calculate performance metrics
        total_return = self.trading_state['cumulative_return']
        avg_daily_return = np.mean(daily_returns)
        volatility = np.std(daily_returns)
        
        # Sharpe ratio (assuming 6% annual risk-free rate)
        risk_free_daily = 0.06 / 252
        excess_returns = daily_returns - risk_free_daily
        sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
        
        # Win rate
        total_days = self.validation_metrics.get('win_days', 0) + self.validation_metrics.get('loss_days', 0)
        win_rate = self.validation_metrics.get('win_days', 0) / total_days if total_days > 0 else 0
        
        # Validation criteria assessment
        validation_criteria = {
            'min_trading_days': 20,
            'min_sharpe_ratio': 1.0,
            'max_drawdown': 0.05,
            'min_win_rate': 0.6
        }
        
        criteria_met = {
            'trading_days': self.trading_state['total_trading_days'] >= validation_criteria['min_trading_days'],
            'sharpe_ratio': sharpe_ratio >= validation_criteria['min_sharpe_ratio'],
            'max_drawdown': self.validation_metrics['max_drawdown'] <= validation_criteria['max_drawdown'],
            'win_rate': win_rate >= validation_criteria['min_win_rate']
        }
        
        validation_score = sum(criteria_met.values()) / len(criteria_met)
        
        report = {
            'validation_period': {
                'start_date': self.trading_state['performance_history'][0]['date'] if self.trading_state['performance_history'] else None,
                'end_date': self.trading_state['last_trading_date'],
                'total_trading_days': self.trading_state['total_trading_days']
            },
            'performance_metrics': {
                'total_return': total_return,
                'average_daily_return': avg_daily_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': self.validation_metrics.get('max_drawdown', 0.0),
                'current_drawdown': self.validation_metrics.get('current_drawdown', 0.0),
                'win_rate': win_rate,
                'win_days': self.validation_metrics.get('win_days', 0),
                'loss_days': self.validation_metrics.get('loss_days', 0)
            },
            'validation_assessment': {
                'criteria_met': criteria_met,
                'validation_score': validation_score,
                'production_ready': validation_score >= 0.8
            },
            'generation_timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Save validation report
        report_file = self.reports_dir / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            self.logger.info(f"Validation report generated: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save validation report: {e}")
        
        return report
    
    def start_automated_trading(self) -> None:
        """Start automated daily shadow trading"""
        self.logger.info("Starting automated shadow trading system...")
        if schedule is None:
            raise RuntimeError("The 'schedule' package is not installed. Install it to use automated mode, or run with --mode manual.")
        
        # Schedule daily trading at 4:00 PM (after market close)
        schedule.every().monday.at("16:00").do(self.run_daily_trading)
        schedule.every().tuesday.at("16:00").do(self.run_daily_trading)
        schedule.every().wednesday.at("16:00").do(self.run_daily_trading)
        schedule.every().thursday.at("16:00").do(self.run_daily_trading)
        schedule.every().friday.at("16:00").do(self.run_daily_trading)
        
        # Schedule monthly report generation
        schedule.every().month.do(self.generate_monthly_report)
        
        # Schedule validation report generation (weekly)
        schedule.every().friday.at("17:00").do(self.generate_validation_report)
        
        print("📅 SHADOW TRADING SCHEDULE:")
        print("  • Daily Trading: Weekdays at 4:00 PM")
        print("  • Monthly Reports: First of each month")
        print("  • Validation Reports: Every Friday at 5:00 PM")
        print("\n🔄 System running... Press Ctrl+C to stop")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("Shadow trading system stopped by user")
            print("\n⏹️ Shadow trading system stopped")
    
    def generate_monthly_report(self) -> None:
        """Generate monthly performance report"""
        try:
            if self.report_generator:
                report = self.report_generator.generate_monthly_report()
                self.logger.info("Monthly report generated successfully")
            else:
                self.logger.warning("Report generator not initialized")
        except Exception as e:
            self.logger.error(f"Failed to generate monthly report: {e}")
    
    def run_manual_trading(self, num_days: int = 1) -> List[Dict[str, Any]]:
        """Run manual shadow trading for specified number of days"""
        results = []
        
        for i in range(num_days):
            trading_date = datetime.now(timezone.utc) - timedelta(days=i)
            result = self.run_daily_trading(trading_date)
            results.append(result)
        
        return results
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            validation_report = self.generate_validation_report()
        except Exception as e:
            self.logger.warning(f"Failed to generate validation report: {e}")
            validation_report = {'validation_assessment': {'validation_score': 0, 'production_ready': False}}
        
        status = {
            'system_active': self.trading_state.get('system_active', False),
            'last_trading_date': self.trading_state.get('last_trading_date'),
            'total_trading_days': self.trading_state.get('total_trading_days', 0),
            'cumulative_return': self.trading_state.get('cumulative_return', 0.0),
            'current_positions_count': len(self.trading_state.get('current_positions', {})),
            'validation_score': validation_report.get('validation_assessment', {}).get('validation_score', 0),
            'production_ready': validation_report.get('validation_assessment', {}).get('production_ready', False)
        }
        
        return status


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Shadow Trading System")
    parser.add_argument('--mode', choices=['auto', 'manual', 'status', 'report'], 
                       default='auto', help='Execution mode')
    parser.add_argument('--days', type=int, default=1, 
                       help='Number of days for manual mode')
    parser.add_argument('--capital', type=float, default=10000000,
                       help='Initial capital (default: ₹1 Crore)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/shadow_trading.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize system
        shadow_system = ComprehensiveShadowTradingSystem(initial_capital=args.capital)
        
        if not shadow_system.initialize_system():
            logger.error("Failed to initialize shadow trading system")
            return
        
        if args.mode == 'auto':
            # Start automated trading
            shadow_system.start_automated_trading()
            
        elif args.mode == 'manual':
            # Run manual trading
            print(f"🔧 Running manual shadow trading for {args.days} day(s)...")
            results = shadow_system.run_manual_trading(args.days)
            
            for result in results:
                print(f"📊 {result['date']}: {result['status']}")
                if 'daily_return' in result:
                    print(f"   Return: {result['daily_return']:.2%}")
            
        elif args.mode == 'status':
            # Show system status
            status = shadow_system.get_system_status()
            
            print("\n📈 SHADOW TRADING SYSTEM STATUS")
            print(f"System Active: {'✅ YES' if status['system_active'] else '❌ NO'}")
            print(f"Last Trading Date: {status['last_trading_date']}")
            print(f"Total Trading Days: {status['total_trading_days']}")
            print(f"Cumulative Return: {status['cumulative_return']:.2%}")
            print(f"Current Positions: {status['current_positions_count']}")
            print(f"Validation Score: {status['validation_score']:.1%}")
            print(f"Production Ready: {'✅ YES' if status['production_ready'] else '❌ NO'}")
            
        elif args.mode == 'report':
            # Generate validation report
            print("📋 Generating validation report...")
            report = shadow_system.generate_validation_report()
            
            if 'error' in report:
                print(f"❌ {report['error']}")
            else:
                print("\n📊 VALIDATION REPORT")
                print(f"Trading Days: {report['validation_period']['total_trading_days']}")
                print(f"Total Return: {report['performance_metrics']['total_return']:.2%}")
                print(f"Sharpe Ratio: {report['performance_metrics']['sharpe_ratio']:.2f}")
                print(f"Max Drawdown: {report['performance_metrics']['max_drawdown']:.2%}")
                print(f"Win Rate: {report['performance_metrics']['win_rate']:.1%}")
                print(f"Validation Score: {report['validation_assessment']['validation_score']:.1%}")
                print(f"Production Ready: {'✅ YES' if report['validation_assessment']['production_ready'] else '❌ NO'}")
        
    except Exception as e:
        logger.error(f"Shadow trading system error: {e}")
        raise


if __name__ == "__main__":
    main()
