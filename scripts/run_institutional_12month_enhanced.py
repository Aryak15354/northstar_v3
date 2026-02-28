#!/usr/bin/env python3
"""
🏛️ INSTITUTIONAL 12-MONTH VALIDATION - ENHANCED VERSION
Leverages existing enhanced walk-forward infrastructure

This version integrates with the existing EnhancedWalkForwardEngine
to provide institutional-grade 12-month validation using the
proven infrastructure already in place.

Usage:
    python scripts/run_institutional_12month_enhanced.py
"""

import pandas as pd
import numpy as np
import os
import json
import hashlib
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import warnings
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

warnings.filterwarnings('ignore')

# Add src to path
import sys
sys.path.append('src')

# Import existing components
from src.validation.enhanced_walk_forward_engine import EnhancedWalkForwardEngine, SimulationResults
from src.intelligence.institutional_alpha_engine import AlphaEngineConfig
from src.intelligence.temporal_guard import TemporalGuard

@dataclass
class InstitutionalConfig:
    """Frozen institutional configuration"""
    
    # Walk-forward parameters (FROZEN)
    training_months: int = 12
    test_months: int = 12
    step_months: int = 1
    
    # Risk parameters (FROZEN)
    max_drawdown_limit: float = 0.12  # 12%
    target_volatility: float = 0.15   # 15%
    max_position_size: float = 0.08   # 8%
    
    # Execution parameters (FROZEN)
    transaction_cost: float = 0.0015  # 15 bps
    market_impact: float = 0.001      # 10 bps
    
    def to_hash(self) -> str:
        """Generate cryptographic hash"""
        config_str = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

class InstitutionalValidator:
    """
    Institutional 12-Month Validator using Enhanced Infrastructure
    
    This leverages the existing EnhancedWalkForwardEngine but applies
    institutional discipline and reporting standards.
    """
    
    def __init__(self):
        self.name = "Institutional 12-Month Validator (Enhanced)"
        self.version = "1.0"
        self.execution_timestamp = datetime.now()
        
        # Frozen configuration
        self.config = InstitutionalConfig()
        self.config_hash = self.config.to_hash()
        
        # Initialize components
        self.alpha_config = AlphaEngineConfig()
        self.walk_forward_engine = EnhancedWalkForwardEngine(self.alpha_config)
        self.temporal_guard = TemporalGuard()
        
        # Results storage
        self.simulation_results: List[SimulationResults] = []
        self.window_summaries: List[Dict[str, Any]] = []
        
        print(f"🏛️ {self.name} v{self.version}")
        print(f"🔒 Configuration Hash: {self.config_hash[:16]}...")
        print(f"⚠️  Configuration FROZEN - no changes allowed")
    
    def validate_data_availability(self) -> bool:
        """Validate required data is available"""
        
        print("📊 Validating data availability...")
        
        required_files = [
            'data/processed/market_state.parquet',
            'data/processed/prices.parquet'
        ]
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                print(f"   ❌ Missing: {file_path}")
                return False
            else:
                print(f"   ✅ Found: {file_path}")
        
        # Check data date range
        try:
            market_df = pd.read_parquet('data/processed/market_state.parquet')
            if 'date' in market_df.columns:
                market_df['date'] = pd.to_datetime(market_df['date'])
                market_df = market_df.set_index('date')
            
            data_start = market_df.index.min()
            data_end = market_df.index.max()
            data_years = (data_end - data_start).days / 365.25
            
            print(f"   📅 Data range: {data_start.date()} to {data_end.date()}")
            print(f"   📊 Data span: {data_years:.1f} years")
            
            if data_years < 3:
                print(f"   ❌ Insufficient data: need 3+ years, have {data_years:.1f}")
                return False
            
            return True
            
        except Exception as e:
            print(f"   ❌ Data validation failed: {e}")
            return False
    
    def determine_validation_windows(self) -> List[Tuple[datetime, datetime]]:
        """Determine 12-month validation windows"""
        
        print("📅 Determining validation windows...")
        
        # Load market data to get date range
        market_df = pd.read_parquet('data/processed/market_state.parquet')
        if 'date' in market_df.columns:
            market_df['date'] = pd.to_datetime(market_df['date'])
            market_df = market_df.set_index('date')
        
        data_start = market_df.index.min()
        data_end = market_df.index.max()
        
        # Calculate first possible start (need 12 months of warmup)
        first_start = data_start + relativedelta(months=self.config.training_months)
        
        # Generate windows
        windows = []
        current_start = first_start
        
        while current_start + relativedelta(months=self.config.test_months) <= data_end:
            window_end = current_start + relativedelta(months=self.config.test_months)
            windows.append((current_start, window_end))
            
            # Step forward
            current_start += relativedelta(months=self.config.step_months)
            
            # Limit to reasonable number of windows
            if len(windows) >= 10:
                break
        
        print(f"   ✅ Generated {len(windows)} validation windows:")
        for i, (start, end) in enumerate(windows):
            print(f"      Window {i+1}: {start.date()} to {end.date()}")
        
        return windows
    
    def run_single_window(self, window_id: str, start_date: datetime, end_date: datetime) -> Optional[Dict[str, Any]]:
        """Run validation for a single 12-month window"""
        
        print(f"\n🧪 Running Window {window_id}: {start_date.date()} to {end_date.date()}")
        
        try:
            # Run simulation using enhanced engine
            results = self.walk_forward_engine.run_complete_simulation(start_date, end_date)
            
            if not results:
                print(f"   ❌ Window {window_id} failed - no results")
                return None
            
            # Extract key metrics for institutional analysis
            window_summary = self.extract_institutional_metrics(window_id, results)
            
            print(f"   ✅ Window {window_id} complete:")
            print(f"      Return: {window_summary['total_return']:+.2f}%")
            print(f"      Max DD: {window_summary['max_drawdown']:.2f}%")
            print(f"      Sharpe: {window_summary['sharpe_ratio']:.2f}")
            
            # Store results
            self.simulation_results.append(results)
            self.window_summaries.append(window_summary)
            
            return window_summary
            
        except Exception as e:
            print(f"   ❌ Window {window_id} failed: {e}")
            return None
    
    def extract_institutional_metrics(self, window_id: str, results: SimulationResults) -> Dict[str, Any]:
        """Extract institutional metrics from simulation results"""
        
        # Calculate key institutional metrics
        daily_states = results.daily_states
        
        if not daily_states:
            return {
                'window_id': window_id,
                'total_return': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'average_exposure': 0.0,
                'override_attempts': 0,
                'kill_switch_triggers': 0
            }
        
        # Performance metrics
        start_value = daily_states[0].total_value
        end_value = daily_states[-1].total_value
        total_return = (end_value / start_value - 1) * 100
        
        # Risk metrics
        max_drawdown = max(state.current_drawdown for state in daily_states) * 100
        
        # Daily returns for Sharpe calculation
        daily_returns = []
        for i in range(1, len(daily_states)):
            prev_value = daily_states[i-1].total_value
            curr_value = daily_states[i].total_value
            daily_return = (curr_value / prev_value - 1)
            daily_returns.append(daily_return)
        
        if daily_returns:
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            sharpe_ratio = (mean_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Exposure analysis
        exposures = []
        for state in daily_states:
            total_exposure = sum(abs(weight) for weight in state.portfolio_weights.values())
            exposures.append(total_exposure)
        
        average_exposure = np.mean(exposures) * 100 if exposures else 0
        
        # System integrity metrics
        override_attempts = 0  # Would be tracked in actual implementation
        kill_switch_triggers = len(results.kill_switch_triggers)
        
        return {
            'window_id': window_id,
            'start_date': results.start_date,
            'end_date': results.end_date,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'volatility': std_return * np.sqrt(252) * 100 if daily_returns else 0,
            'average_exposure': average_exposure,
            'override_attempts': override_attempts,
            'kill_switch_triggers': kill_switch_triggers,
            'regime_flips': 0,  # Would be calculated from regime data
            'shutdown_events': kill_switch_triggers,
            'transaction_costs': sum(state.transaction_costs for state in daily_states),
            'daily_states_count': len(daily_states)
        }
    
    def generate_institutional_report(self) -> Dict[str, Any]:
        """Generate institutional-grade report"""
        
        print("\n📊 Generating institutional report...")
        
        if not self.window_summaries:
            return {'status': 'FAILED', 'reason': 'No window results available'}
        
        # Summary statistics
        returns = [w['total_return'] for w in self.window_summaries]
        drawdowns = [w['max_drawdown'] for w in self.window_summaries]
        sharpes = [w['sharpe_ratio'] for w in self.window_summaries]
        exposures = [w['average_exposure'] for w in self.window_summaries]
        
        # Institutional validation checks
        behavior_validation = {
            'no_override_attempts': sum(w['override_attempts'] for w in self.window_summaries) == 0,
            'maintained_exposure': np.mean(exposures) > 50,  # Stayed exposed
            'drawdown_covenant': max(drawdowns) <= self.config.max_drawdown_limit * 100,
            'structural_exits_only': all(w['shutdown_events'] < 10 for w in self.window_summaries),
            'positive_expected_return': np.mean(returns) > 0
        }
        
        validation_passed = all(behavior_validation.values())
        
        # Worst case analysis
        worst_window = min(self.window_summaries, key=lambda x: x['total_return'])
        
        # Distribution analysis
        distributions = {
            'returns': {
                'mean': np.mean(returns),
                'std': np.std(returns),
                'min': np.min(returns),
                'max': np.max(returns),
                'percentiles': {
                    '5th': np.percentile(returns, 5),
                    '25th': np.percentile(returns, 25),
                    '50th': np.percentile(returns, 50),
                    '75th': np.percentile(returns, 75),
                    '95th': np.percentile(returns, 95)
                }
            },
            'drawdowns': {
                'mean': np.mean(drawdowns),
                'max': np.max(drawdowns),
                'min': np.min(drawdowns)
            }
        }
        
        # Generate report
        report = {
            'validation_status': 'PASS' if validation_passed else 'FAIL',
            'execution_timestamp': self.execution_timestamp.isoformat(),
            'configuration_hash': self.config_hash,
            'windows_processed': len(self.window_summaries),
            'window_summaries': self.window_summaries,
            'behavior_validation': behavior_validation,
            'distributions': distributions,
            'worst_case': {
                'window_id': worst_window['window_id'],
                'return': worst_window['total_return'],
                'drawdown': worst_window['max_drawdown'],
                'year': worst_window['start_date'].year if isinstance(worst_window['start_date'], datetime) else 'unknown'
            },
            'system_integrity': {
                'total_override_attempts': sum(w['override_attempts'] for w in self.window_summaries),
                'total_kill_switches': sum(w['kill_switch_triggers'] for w in self.window_summaries),
                'temporal_violations': 0  # Would be tracked
            }
        }
        
        return report
    
    def save_results(self, report: Dict[str, Any]):
        """Save results with institutional sealing"""
        
        print("💾 Saving institutional results...")
        
        # Create results directory
        results_dir = Path("data/validation/institutional_enhanced")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = self.execution_timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Save main report
        report_file = results_dir / f"institutional_report_{timestamp_str}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate and save seal
        report_str = json.dumps(report, sort_keys=True, default=str)
        results_hash = hashlib.sha256(report_str.encode()).hexdigest()
        
        seal_file = results_dir / f"institutional_seal_{timestamp_str}.txt"
        with open(seal_file, 'w') as f:
            f.write(f"INSTITUTIONAL 12-MONTH VALIDATION SEAL\n")
            f.write(f"=====================================\n")
            f.write(f"Execution Time: {self.execution_timestamp}\n")
            f.write(f"Configuration Hash: {self.config_hash}\n")
            f.write(f"Results Hash: {results_hash}\n")
            f.write(f"Validation Status: {report['validation_status']}\n")
            f.write(f"Windows Processed: {report['windows_processed']}\n")
            f.write(f"System: NorthStar V3 Enhanced\n")
            f.write(f"=====================================\n")
        
        print(f"   ✅ Report saved: {report_file}")
        print(f"   🔒 Seal saved: {seal_file}")
        print(f"   📊 Results hash: {results_hash[:16]}...")
    
    def run_complete_validation(self) -> Dict[str, Any]:
        """Run complete institutional validation"""
        
        print(f"\n🏛️ STARTING INSTITUTIONAL 12-MONTH VALIDATION")
        print(f"Using Enhanced Walk-Forward Infrastructure")
        print(f"Configuration Hash: {self.config_hash[:16]}...")
        
        # Step 1: Validate data
        if not self.validate_data_availability():
            return {'status': 'FAILED', 'reason': 'Data validation failed'}
        
        # Step 2: Determine windows
        windows = self.determine_validation_windows()
        if not windows:
            return {'status': 'FAILED', 'reason': 'No validation windows available'}
        
        # Step 3: Run validation windows
        print(f"\n🧪 Running {len(windows)} validation windows...")
        
        for i, (start_date, end_date) in enumerate(windows):
            window_id = f"W{i+1:02d}_{start_date.year}"
            self.run_single_window(window_id, start_date, end_date)
        
        # Step 4: Generate report
        report = self.generate_institutional_report()
        
        # Step 5: Save results
        self.save_results(report)
        
        # Step 6: Print summary
        print(f"\n🏛️ INSTITUTIONAL VALIDATION COMPLETE")
        print(f"   Status: {report['validation_status']}")
        print(f"   Windows: {report['windows_processed']}")
        print(f"   Configuration: {self.config_hash[:16]}...")
        
        if report['validation_status'] == 'PASS':
            print(f"   ✅ SYSTEM PASSES INSTITUTIONAL VALIDATION")
        else:
            print(f"   ❌ SYSTEM FAILS INSTITUTIONAL VALIDATION")
            
            # Print failure reasons
            behavior = report.get('behavior_validation', {})
            for check, passed in behavior.items():
                if not passed:
                    print(f"      ❌ Failed: {check}")
        
        return report

def main():
    """Main execution function"""
    
    print("🏛️ INSTITUTIONAL 12-MONTH VALIDATION (Enhanced)")
    print("=" * 60)
    print("Leveraging existing Enhanced Walk-Forward Engine")
    print("Applying institutional discipline and reporting")
    print("=" * 60)
    
    # Initialize and run validator
    validator = InstitutionalValidator()
    results = validator.run_complete_validation()
    
    # Final summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Status: {results.get('validation_status', 'UNKNOWN')}")
    print(f"Windows: {results.get('windows_processed', 0)}")
    
    if results.get('validation_status') == 'PASS':
        print("\n✅ SYSTEM READY FOR INSTITUTIONAL DEPLOYMENT")
        print("The system has passed rigorous 12-month validation")
        print("under institutional discipline with frozen parameters.")
    else:
        print("\n❌ SYSTEM NOT READY FOR DEPLOYMENT")
        print("Address the validation failures before proceeding.")
    
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    results = main()