#!/usr/bin/env python3
"""
🔥 BRUTAL PERIOD STRESS TESTER
Stress-test the system against specific brutal historical periods

This tests system behavior during:
- 2008 Financial Crisis
- 2020 COVID Crash
- 2022 Inflation/Rate Shock
- Custom brutal periods

Usage:
    python scripts/stress_test_brutal_periods.py --period 2008
    python scripts/stress_test_brutal_periods.py --period 2020
    python scripts/stress_test_brutal_periods.py --period 2022
    python scripts/stress_test_brutal_periods.py --period all
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
import numpy as np
import warnings
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import dual engine system
from src.intelligence.dual_engine_coordinator import DualEngineCoordinator
from src.intelligence.crisis_engine import NorthstarCrisisEngine
from src.intelligence.crisis_conviction_contract import CrisisConvictionContract

warnings.filterwarnings('ignore')

@dataclass
class BrutalPeriodConfig:
    """Configuration for a brutal historical period"""
    
    name: str
    start_date: str
    end_date: str
    description: str
    expected_challenges: List[str]
    success_criteria: Dict[str, Any]

class BrutalPeriodStressTester:
    """
    Stress test system against brutal historical periods
    
    This answers: "How does the system behave when markets are trying to kill it?"
    """
    
    def __init__(self):
        self.name = "Brutal Period Stress Tester"
        self.version = "1.0.0"
        
        # Define brutal periods (EXPANDED)
        self.brutal_periods = {
            '2008': BrutalPeriodConfig(
                name="2008 Financial Crisis",
                start_date="2007-07-01",
                end_date="2009-03-31",
                description="Subprime mortgage crisis, Lehman collapse, credit freeze",
                expected_challenges=[
                    "Extreme volatility spikes",
                    "Liquidity evaporation", 
                    "Correlation breakdown",
                    "Flight to quality",
                    "Credit market freeze"
                ],
                success_criteria={
                    'max_drawdown_limit': 25.0,  # 25% max acceptable
                    'min_exposure_during_crisis': 15.0,  # FIXED: Must stay exposed
                    'max_regime_flip_frequency': 0.3,  # Max 30% of days
                    'recovery_time_limit_months': 18
                }
            ),
            
            '2020': BrutalPeriodConfig(
                name="2020 COVID Crash",
                start_date="2020-01-01",
                end_date="2020-12-31",
                description="Pandemic lockdowns, circuit breakers, unprecedented intervention",
                expected_challenges=[
                    "Fastest bear market in history",
                    "Circuit breaker triggers",
                    "Unprecedented fiscal/monetary response",
                    "Sector rotation extremes",
                    "Volatility regime shifts"
                ],
                success_criteria={
                    'max_drawdown_limit': 20.0,  # 20% max acceptable
                    'min_exposure_during_crisis': 15.0,  # FIXED: Must stay exposed
                    'max_regime_flip_frequency': 0.4,  # Max 40% of days
                    'recovery_time_limit_months': 12
                }
            ),
            
            '2022': BrutalPeriodConfig(
                name="2022 Inflation/Rate Shock",
                start_date="2021-11-01", 
                end_date="2022-12-31",
                description="Inflation surge, aggressive rate hikes, growth/value rotation",
                expected_challenges=[
                    "Inflation breakout",
                    "Aggressive Fed tightening",
                    "Growth stock collapse",
                    "Bond/equity correlation breakdown",
                    "Crypto contagion"
                ],
                success_criteria={
                    'max_drawdown_limit': 18.0,  # 18% max acceptable
                    'min_exposure_during_crisis': 20.0,  # FIXED: Must stay exposed
                    'max_regime_flip_frequency': 0.25,  # Max 25% of days
                    'recovery_time_limit_months': 15
                }
            ),
            
            # NEW BRUTAL PERIODS ADDED
            '2000': BrutalPeriodConfig(
                name="2000 Dot-Com Crash",
                start_date="2000-03-01",
                end_date="2002-10-31",
                description="Tech bubble burst, NASDAQ collapse, recession",
                expected_challenges=[
                    "Tech stock collapse",
                    "Valuation reset",
                    "Growth to value rotation",
                    "Corporate scandals",
                    "Economic recession"
                ],
                success_criteria={
                    'max_drawdown_limit': 30.0,  # 30% max (longer period)
                    'min_exposure_during_crisis': 15.0,
                    'max_regime_flip_frequency': 0.35,
                    'recovery_time_limit_months': 24
                }
            ),
            
            '2018': BrutalPeriodConfig(
                name="2018 Volatility Spike",
                start_date="2018-01-01",
                end_date="2018-12-31",
                description="VIX spike, trade wars, Fed tightening fears",
                expected_challenges=[
                    "VIX explosion",
                    "Trade war escalation",
                    "Fed tightening fears",
                    "Emerging market stress",
                    "Oil price volatility"
                ],
                success_criteria={
                    'max_drawdown_limit': 15.0,  # 15% max
                    'min_exposure_during_crisis': 20.0,
                    'max_regime_flip_frequency': 0.3,
                    'recovery_time_limit_months': 9
                }
            ),
            
            '2015': BrutalPeriodConfig(
                name="2015 China Devaluation Crisis",
                start_date="2015-06-01",
                end_date="2016-02-29",
                description="China devaluation, commodity collapse, EM crisis",
                expected_challenges=[
                    "China devaluation shock",
                    "Commodity price collapse",
                    "Emerging market crisis",
                    "Oil price crash",
                    "Currency volatility"
                ],
                success_criteria={
                    'max_drawdown_limit': 20.0,
                    'min_exposure_during_crisis': 18.0,
                    'max_regime_flip_frequency': 0.35,
                    'recovery_time_limit_months': 12
                }
            ),
            
            '2011': BrutalPeriodConfig(
                name="2011 European Debt Crisis",
                start_date="2011-05-01",
                end_date="2012-01-31",
                description="European sovereign debt crisis, Greek default fears",
                expected_challenges=[
                    "Sovereign debt crisis",
                    "Greek default fears",
                    "Euro breakup risk",
                    "Banking sector stress",
                    "Contagion effects"
                ],
                success_criteria={
                    'max_drawdown_limit': 22.0,
                    'min_exposure_during_crisis': 15.0,
                    'max_regime_flip_frequency': 0.4,
                    'recovery_time_limit_months': 15
                }
            )
        }
        
        print(f"🔥 {self.name} v{self.version}")
        print("Testing system survival under brutal market conditions")
    
    def load_market_data_for_period(self, period_config: BrutalPeriodConfig) -> pd.DataFrame:
        """Load and prepare market data for the brutal period using real historical data"""
        
        print(f"\n📊 Loading data for {period_config.name}")
        print(f"Period: {period_config.start_date} to {period_config.end_date}")
        
        try:
            # Load real historical price data from extended prices folder
            import glob
            import os
            
            price_files = glob.glob('data/raw/prices_daily/*.csv')
            if not price_files:
                print(f"⚠️  No historical price files found, creating synthetic data")
                return self._create_synthetic_brutal_period(period_config)
            
            # Load a representative sample of stocks for market index calculation
            sample_stocks = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 
                           'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS']
            
            all_data = []
            for stock in sample_stocks:
                file_path = f'data/raw/prices_daily/{stock}.csv'
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    df['Date'] = pd.to_datetime(df['Date'])
                    df['Symbol'] = stock
                    df['Return'] = df['Close'].pct_change()
                    all_data.append(df[['Date', 'Close', 'Return', 'Symbol']])
            
            if not all_data:
                print(f"⚠️  No valid stock data loaded, creating synthetic data")
                return self._create_synthetic_brutal_period(period_config)
            
            # Combine all stock data
            combined_data = pd.concat(all_data, ignore_index=True)
            
            # Create market index (equal-weighted average of sample stocks)
            market_index = combined_data.groupby('Date').agg({
                'Return': 'mean',
                'Close': 'mean'
            }).reset_index()
            
            # Filter to period
            start_date = pd.to_datetime(period_config.start_date)
            end_date = pd.to_datetime(period_config.end_date)
            
            period_data = market_index[
                (market_index['Date'] >= start_date) & 
                (market_index['Date'] <= end_date)
            ].copy()
            
            if len(period_data) < 100:
                print(f"⚠️  Limited data for period: {len(period_data)} records, creating synthetic data")
                return self._create_synthetic_brutal_period(period_config)
            
            daily_returns = period_data['Return'].fillna(0)
            
            # Enhance with brutal period characteristics
            daily_returns = self._enhance_with_brutal_characteristics(
                daily_returns, period_config
            )
            
            # Calculate volatility and regime
            volatility = daily_returns.rolling(20).std() * np.sqrt(252)
            
            # Create market data
            dates = period_data['Date']
            regimes = self._classify_brutal_regimes(daily_returns, volatility, period_config)
            
            market_data = pd.DataFrame({
                'date': dates,
                'market_return': daily_returns.values,
                'regime': regimes,
                'volatility': volatility.fillna(0.30).values,  # Higher default vol
                'period_phase': self._identify_period_phases(dates, period_config)
            })
            
            print(f"✅ Prepared {len(market_data)} days of brutal market data")
            return market_data
            
        except Exception as e:
            print(f"❌ Failed to load period data: {e}")
            return self._create_synthetic_brutal_period(period_config)
    
    def _create_synthetic_brutal_period(self, period_config: BrutalPeriodConfig) -> pd.DataFrame:
        """Create synthetic brutal period data based on historical characteristics"""
        
        print(f"🔧 Creating synthetic brutal period for {period_config.name}")
        
        start_date = pd.to_datetime(period_config.start_date)
        end_date = pd.to_datetime(period_config.end_date)
        
        # Generate date range
        dates = pd.date_range(start_date, end_date, freq='D')
        dates = dates[dates.weekday < 5]  # Business days only
        
        np.random.seed(42)  # Reproducible
        
        # Create brutal return patterns based on period type
        if '2008' in period_config.name:
            returns = self._generate_2008_pattern(len(dates))
        elif '2020' in period_config.name:
            returns = self._generate_2020_pattern(len(dates))
        elif '2022' in period_config.name:
            returns = self._generate_2022_pattern(len(dates))
        else:
            returns = self._generate_generic_brutal_pattern(len(dates))
        
        # Calculate volatility
        volatility = pd.Series(returns).rolling(20).std() * np.sqrt(252)
        
        # Classify regimes
        regimes = self._classify_brutal_regimes(
            pd.Series(returns, index=dates), 
            volatility, 
            period_config
        )
        
        market_data = pd.DataFrame({
            'date': dates,
            'market_return': returns,
            'regime': regimes,
            'volatility': volatility.fillna(0.30).values,
            'period_phase': self._identify_period_phases(dates, period_config)
        })
        
        return market_data
    
    def _generate_2008_pattern(self, n_days: int) -> np.ndarray:
        """Generate 2008-style return pattern"""
        
        # 2008 characteristics: Gradual decline, then crash, slow recovery
        returns = np.random.normal(0, 0.02, n_days)  # Base volatility
        
        # Add trend components
        crash_start = int(n_days * 0.3)  # Crash starts 30% through
        crash_end = int(n_days * 0.7)    # Ends 70% through
        
        # Pre-crash: Gradual decline
        returns[:crash_start] += np.linspace(0, -0.003, crash_start)
        
        # Crash phase: High volatility, negative bias
        crash_length = crash_end - crash_start
        returns[crash_start:crash_end] = np.random.normal(-0.002, 0.04, crash_length)
        
        # Add some extreme days
        extreme_days = np.random.choice(
            range(crash_start, crash_end), 
            size=max(1, crash_length // 10), 
            replace=False
        )
        returns[extreme_days] = np.random.uniform(-0.08, -0.05, len(extreme_days))
        
        # Recovery: Volatile but upward bias
        returns[crash_end:] += np.linspace(-0.001, 0.002, n_days - crash_end)
        
        return np.clip(returns, -0.10, 0.10)  # Realistic limits
    
    def _generate_2020_pattern(self, n_days: int) -> np.ndarray:
        """Generate 2020-style return pattern"""
        
        # 2020 characteristics: Sharp crash, sharp recovery
        returns = np.random.normal(0, 0.015, n_days)
        
        # Sharp crash in March (assume ~25% through year)
        crash_start = int(n_days * 0.2)
        crash_end = int(n_days * 0.3)
        
        # Pre-crash: Normal
        returns[:crash_start] = np.random.normal(0.001, 0.015, crash_start)
        
        # Crash: Extreme volatility and negative returns
        crash_length = crash_end - crash_start
        returns[crash_start:crash_end] = np.random.normal(-0.005, 0.06, crash_length)
        
        # Add circuit breaker days
        circuit_breaker_days = np.random.choice(
            range(crash_start, crash_end),
            size=max(1, crash_length // 5),
            replace=False
        )
        returns[circuit_breaker_days] = np.random.uniform(-0.12, -0.07, len(circuit_breaker_days))
        
        # Recovery: Strong upward bias with high volatility
        recovery_length = n_days - crash_end
        returns[crash_end:] = np.random.normal(0.003, 0.025, recovery_length)
        
        return np.clip(returns, -0.15, 0.15)  # Allow extreme moves
    
    def _generate_2022_pattern(self, n_days: int) -> np.ndarray:
        """Generate 2022-style return pattern"""
        
        # 2022 characteristics: Grinding bear market, rate shock
        returns = np.random.normal(-0.0005, 0.02, n_days)  # Slight negative bias
        
        # Add rate shock periods
        shock_periods = [
            (int(n_days * 0.2), int(n_days * 0.3)),  # Early shock
            (int(n_days * 0.5), int(n_days * 0.6)),  # Mid-year shock
            (int(n_days * 0.8), int(n_days * 0.9))   # Late shock
        ]
        
        for start, end in shock_periods:
            shock_length = end - start
            returns[start:end] = np.random.normal(-0.002, 0.03, shock_length)
        
        # Add some relief rallies
        rally_periods = [
            (int(n_days * 0.35), int(n_days * 0.45)),
            (int(n_days * 0.65), int(n_days * 0.75))
        ]
        
        for start, end in rally_periods:
            rally_length = end - start
            returns[start:end] = np.random.normal(0.002, 0.02, rally_length)
        
        return np.clip(returns, -0.08, 0.08)
    
    def _generate_generic_brutal_pattern(self, n_days: int) -> np.ndarray:
        """Generate generic brutal market pattern"""
        
        returns = np.random.normal(-0.001, 0.025, n_days)
        
        # Add periodic stress
        for i in range(0, n_days, 30):  # Every 30 days
            stress_length = min(10, n_days - i)
            returns[i:i+stress_length] = np.random.normal(-0.003, 0.04, stress_length)
        
        return np.clip(returns, -0.08, 0.08)
    
    def _enhance_with_brutal_characteristics(self, returns: pd.Series, 
                                          period_config: BrutalPeriodConfig) -> pd.Series:
        """Enhance real data with brutal period characteristics"""
        
        enhanced_returns = returns.copy()
        
        # Increase volatility during known stress periods
        if '2008' in period_config.name:
            # Add Lehman shock (September 2008)
            lehman_date = pd.to_datetime('2008-09-15')
            if lehman_date in enhanced_returns.index:
                shock_window = 10  # 10 days of extreme stress
                lehman_idx = enhanced_returns.index.get_loc(lehman_date)
                start_idx = max(0, lehman_idx - shock_window//2)
                end_idx = min(len(enhanced_returns), lehman_idx + shock_window//2)
                
                # Add extreme negative returns
                shock_returns = np.random.normal(-0.05, 0.03, end_idx - start_idx)
                enhanced_returns.iloc[start_idx:end_idx] = shock_returns
        
        return enhanced_returns
    
    def _classify_brutal_regimes(self, returns: pd.Series, volatility: pd.Series,
                               period_config: BrutalPeriodConfig) -> List[str]:
        """Classify regimes during brutal periods"""
        
        regimes = []
        
        for i in range(len(returns)):
            if i < 20:
                regimes.append('CRISIS')
                continue
            
            recent_vol = volatility.iloc[i] if not pd.isna(volatility.iloc[i]) else 0.30
            recent_return = returns.iloc[i-19:i+1].mean() * 252
            daily_return = returns.iloc[i]
            
            # More aggressive regime classification for brutal periods
            if recent_vol > 0.40 or daily_return < -0.05:
                regime = 'PANIC'
            elif recent_vol > 0.30 or daily_return < -0.03:
                regime = 'CRISIS'
            elif recent_vol > 0.25:
                regime = 'STRESS'
            elif recent_return < -0.15:
                regime = 'BEAR'
            elif recent_return > 0.10 and recent_vol < 0.20:
                regime = 'RECOVERY'
            else:
                regime = 'VOLATILE'
            
            regimes.append(regime)
        
        return regimes
    
    def _identify_period_phases(self, dates: pd.DatetimeIndex, 
                              period_config: BrutalPeriodConfig) -> List[str]:
        """Identify phases within the brutal period"""
        
        total_days = len(dates)
        phases = []
        
        for i, date in enumerate(dates):
            progress = i / total_days
            
            if '2008' in period_config.name:
                if progress < 0.3:
                    phase = 'PRE_CRISIS'
                elif progress < 0.7:
                    phase = 'CRISIS'
                else:
                    phase = 'RECOVERY'
            elif '2020' in period_config.name:
                if progress < 0.2:
                    phase = 'PRE_CRASH'
                elif progress < 0.3:
                    phase = 'CRASH'
                else:
                    phase = 'RECOVERY'
            elif '2022' in period_config.name:
                if progress < 0.25:
                    phase = 'EARLY_DECLINE'
                elif progress < 0.75:
                    phase = 'GRINDING_BEAR'
                else:
                    phase = 'LATE_CYCLE'
            else:
                phase = 'STRESS'
            
            phases.append(phase)
        
        return phases
    
    def run_brutal_period_test(self, period_key: str) -> Dict[str, Any]:
        """Run stress test for a specific brutal period"""
        
        if period_key not in self.brutal_periods:
            raise ValueError(f"Unknown period: {period_key}")
        
        period_config = self.brutal_periods[period_key]
        
        print(f"\n🔥 STRESS TESTING: {period_config.name}")
        print(f"Description: {period_config.description}")
        print("Expected challenges:")
        for challenge in period_config.expected_challenges:
            print(f"  - {challenge}")
        
        # Load period data
        market_data = self.load_market_data_for_period(period_config)
        
        # Run simulation
        results = self._simulate_brutal_period(market_data, period_config)
        
        # Evaluate against success criteria
        evaluation = self._evaluate_brutal_period_performance(results, period_config)
        
        return {
            'period_config': asdict(period_config),
            'simulation_results': results,
            'evaluation': evaluation,
            'market_data_summary': {
                'total_days': len(market_data),
                'date_range': f"{market_data['date'].min().date()} to {market_data['date'].max().date()}",
                'avg_daily_return': market_data['market_return'].mean(),
                'volatility': market_data['market_return'].std() * np.sqrt(252),
                'worst_day': market_data['market_return'].min(),
                'best_day': market_data['market_return'].max()
            }
        }
    
    def _simulate_brutal_period(self, market_data: pd.DataFrame, 
                              period_config: BrutalPeriodConfig) -> Dict[str, Any]:
        """Simulate system behavior during brutal period using dual engine system"""
        
        print(f"🧪 Simulating system behavior during {period_config.name}")
        
        # Initialize dual engine system
        dual_engine = DualEngineCoordinator()
        
        # Initialize portfolio
        portfolio_value = 100_000_000.0  # $100M
        peak_value = portfolio_value
        
        # Tracking arrays
        daily_values = []
        daily_returns = []
        daily_exposures = []
        regime_changes = []
        shutdown_events = []
        crisis_activations = []
        trend_activations = []
        
        # State variables
        current_regime = 'NORMAL'
        current_exposure = 0.0
        
        # Process each day
        for i, row in market_data.iterrows():
            date = row['date']
            market_return = row['market_return']
            
            # Get current market data window for dual engine
            current_window = market_data.iloc[:i+1] if i >= 20 else market_data.iloc[:21]
            
            # Get dual engine allocation
            allocation = dual_engine.coordinate_engine_allocations(current_window, date)
            
            # Track regime changes
            if allocation.regime.value != current_regime:
                regime_changes.append({
                    'date': date,
                    'from': current_regime,
                    'to': allocation.regime.value
                })
                current_regime = allocation.regime.value
            
            # Track engine activations
            if allocation.crisis_allocation > 0:
                crisis_activations.append({
                    'date': date,
                    'allocation': allocation.crisis_allocation,
                    'regime': allocation.regime.value
                })
            
            if allocation.trend_allocation > 0:
                trend_activations.append({
                    'date': date,
                    'allocation': allocation.trend_allocation,
                    'regime': allocation.regime.value
                })
            
            # Use dual engine total allocation
            target_exposure = allocation.total_allocation
            
            # Check for shutdown conditions
            current_drawdown = (peak_value - portfolio_value) / peak_value
            if current_drawdown >= 0.15:  # 15% shutdown threshold
                target_exposure = 0.0
                shutdown_events.append({
                    'date': date,
                    'drawdown': current_drawdown,
                    'reason': 'DRAWDOWN_LIMIT'
                })
            
            # Calculate portfolio return
            portfolio_return = market_return * current_exposure
            
            # Apply transaction costs for exposure changes
            if abs(target_exposure - current_exposure) > 0.05:
                cost_multiplier = 3.0 if allocation.regime.value in ['PANIC', 'HOSTILE'] else 1.5
                transaction_cost = abs(target_exposure - current_exposure) * 0.002 * cost_multiplier
                portfolio_return -= transaction_cost
            
            # Update portfolio
            portfolio_value *= (1 + portfolio_return)
            
            # Track metrics
            daily_values.append(portfolio_value)
            daily_returns.append(portfolio_return)
            daily_exposures.append(current_exposure)
            
            # Update peak for drawdown calculation
            if portfolio_value > peak_value:
                peak_value = portfolio_value
            
            # Update exposure
            current_exposure = target_exposure
        
        # Calculate final metrics
        total_return = (portfolio_value / 100_000_000.0 - 1) * 100
        max_drawdown = max(0, (peak_value - min(daily_values)) / peak_value * 100)
        
        returns_array = np.array(daily_returns)
        volatility = np.std(returns_array) * np.sqrt(252) * 100
        sharpe = (np.mean(returns_array) * 252) / (volatility / 100) if volatility > 0 else 0
        
        # Calculate recovery time
        recovery_days = 0
        if max_drawdown > 5:  # If significant drawdown occurred
            min_value = min(daily_values)
            min_idx = daily_values.index(min_value)
            
            # Find recovery to 95% of peak
            recovery_target = peak_value * 0.95
            for j in range(min_idx, len(daily_values)):
                if daily_values[j] >= recovery_target:
                    recovery_days = j - min_idx
                    break
            else:
                recovery_days = len(daily_values) - min_idx  # Never recovered
        
        return {
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'avg_exposure': np.mean(daily_exposures) * 100,
            'min_exposure': min(daily_exposures) * 100,
            'max_exposure': max(daily_exposures) * 100,
            'regime_changes': len(regime_changes),
            'shutdown_events': len(shutdown_events),
            'recovery_days': recovery_days,
            'worst_day_return': min(daily_returns) * 100,
            'best_day_return': max(daily_returns) * 100,
            'regime_change_details': regime_changes,
            'shutdown_details': shutdown_events,
            # Dual engine specific metrics
            'crisis_activations': len(crisis_activations),
            'trend_activations': len(trend_activations),
            'crisis_activation_details': crisis_activations,
            'trend_activation_details': trend_activations,
            'dual_engine_coordination': dual_engine.get_coordination_diagnostics()
        }
    
    def _calculate_brutal_period_exposure(self, regime: str, phase: str, 
                                        market_return: float, volatility: float) -> float:
        """Calculate target exposure during brutal periods"""
        
        # Base exposure by regime (very conservative during crisis)
        regime_exposures = {
            'PANIC': 0.0,      # Full cash during panic
            'CRISIS': 0.1,     # Minimal exposure during crisis
            'STRESS': 0.2,     # Low exposure during stress
            'BEAR': 0.3,       # Moderate exposure in bear market
            'VOLATILE': 0.4,   # Moderate exposure in volatile times
            'RECOVERY': 0.6,   # Higher exposure during recovery
            'NORMAL': 0.5      # Normal exposure
        }
        
        base_exposure = regime_exposures.get(regime, 0.3)
        
        # Adjust based on phase
        phase_multipliers = {
            'PRE_CRISIS': 0.8,
            'PRE_CRASH': 0.7,
            'CRISIS': 0.3,
            'CRASH': 0.1,
            'RECOVERY': 1.2,
            'GRINDING_BEAR': 0.5,
            'EARLY_DECLINE': 0.6,
            'LATE_CYCLE': 0.7,
            'STRESS': 0.4
        }
        
        phase_multiplier = phase_multipliers.get(phase, 1.0)
        target_exposure = base_exposure * phase_multiplier
        
        # Further reduce exposure on extreme down days
        if market_return < -0.05:  # -5% day
            target_exposure *= 0.5
        elif market_return < -0.03:  # -3% day
            target_exposure *= 0.7
        
        # Increase exposure on extreme up days (potential oversold bounce)
        if market_return > 0.05:  # +5% day
            target_exposure = min(target_exposure * 1.3, 0.8)
        
        return max(0.0, min(1.0, target_exposure))
    
    def _evaluate_brutal_period_performance(self, results: Dict[str, Any], 
                                          period_config: BrutalPeriodConfig) -> Dict[str, Any]:
        """Evaluate performance against success criteria"""
        
        criteria = period_config.success_criteria
        evaluation = {}
        
        # Check max drawdown
        max_dd_ok = results['max_drawdown'] <= criteria['max_drawdown_limit']
        evaluation['max_drawdown_check'] = {
            'passed': max_dd_ok,
            'actual': results['max_drawdown'],
            'limit': criteria['max_drawdown_limit'],
            'status': '✅ PASS' if max_dd_ok else '❌ FAIL'
        }
        
        # Check minimum exposure during crisis
        min_exp_ok = results['min_exposure'] >= criteria['min_exposure_during_crisis']
        evaluation['min_exposure_check'] = {
            'passed': min_exp_ok,
            'actual': results['min_exposure'],
            'limit': criteria['min_exposure_during_crisis'],
            'status': '✅ PASS' if min_exp_ok else '❌ FAIL'
        }
        
        # Check regime flip frequency
        total_days = len(results.get('regime_change_details', []))
        flip_frequency = results['regime_changes'] / max(1, total_days) if total_days > 0 else 0
        flip_freq_ok = flip_frequency <= criteria['max_regime_flip_frequency']
        evaluation['regime_flip_check'] = {
            'passed': flip_freq_ok,
            'actual': flip_frequency,
            'limit': criteria['max_regime_flip_frequency'],
            'status': '✅ PASS' if flip_freq_ok else '❌ FAIL'
        }
        
        # Check recovery time
        recovery_months = results['recovery_days'] / 30.0  # Approximate months
        recovery_ok = recovery_months <= criteria['recovery_time_limit_months']
        evaluation['recovery_time_check'] = {
            'passed': recovery_ok,
            'actual_days': results['recovery_days'],
            'actual_months': recovery_months,
            'limit_months': criteria['recovery_time_limit_months'],
            'status': '✅ PASS' if recovery_ok else '❌ FAIL'
        }
        
        # Overall assessment
        all_checks = [
            evaluation['max_drawdown_check']['passed'],
            evaluation['min_exposure_check']['passed'],
            evaluation['regime_flip_check']['passed'],
            evaluation['recovery_time_check']['passed']
        ]
        
        evaluation['overall_assessment'] = {
            'passed': all(all_checks),
            'checks_passed': sum(all_checks),
            'total_checks': len(all_checks),
            'status': '✅ SYSTEM SURVIVES BRUTAL PERIOD' if all(all_checks) else '❌ SYSTEM FAILS BRUTAL PERIOD'
        }
        
        return evaluation
    
    def run_all_brutal_periods(self) -> Dict[str, Any]:
        """Run stress tests for all brutal periods"""
        
        print(f"\n🔥 RUNNING ALL BRUTAL PERIOD STRESS TESTS")
        print("=" * 60)
        
        all_results = {}
        
        for period_key in self.brutal_periods.keys():
            try:
                results = self.run_brutal_period_test(period_key)
                all_results[period_key] = results
                
                # Print summary
                evaluation = results['evaluation']['overall_assessment']
                print(f"\n{evaluation['status']}")
                print(f"Period: {results['period_config']['name']}")
                print(f"Checks: {evaluation['checks_passed']}/{evaluation['total_checks']}")
                
            except Exception as e:
                print(f"❌ Failed to test {period_key}: {e}")
                all_results[period_key] = {'error': str(e)}
        
        # Overall summary
        successful_periods = sum(1 for r in all_results.values() 
                               if 'evaluation' in r and 
                               r['evaluation']['overall_assessment']['passed'])
        
        total_periods = len(self.brutal_periods)
        
        print(f"\n" + "=" * 60)
        print(f"BRUTAL PERIOD STRESS TEST SUMMARY")
        print(f"=" * 60)
        print(f"Periods Survived: {successful_periods}/{total_periods}")
        
        if successful_periods == total_periods:
            print("✅ SYSTEM SURVIVES ALL BRUTAL PERIODS")
            print("The system demonstrates institutional-grade crisis resilience")
        else:
            print("❌ SYSTEM FAILS SOME BRUTAL PERIODS")
            print("Address crisis management before live deployment")
        
        return {
            'summary': {
                'periods_survived': successful_periods,
                'total_periods': total_periods,
                'survival_rate': successful_periods / total_periods,
                'overall_status': 'PASS' if successful_periods == total_periods else 'FAIL'
            },
            'detailed_results': all_results
        }
    
    def save_stress_test_results(self, results: Dict[str, Any]):
        """Save stress test results"""
        
        results_dir = Path("data/validation/brutal_periods")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = results_dir / f"brutal_period_stress_test_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Stress test results saved: {results_file}")
        return results_file

def main():
    """Main execution"""
    
    parser = argparse.ArgumentParser(description='Brutal Period Stress Tester')
    parser.add_argument('--period', choices=['2008', '2020', '2022', 'all'], 
                       default='all', help='Period to test')
    
    args = parser.parse_args()
    
    print("🔥 BRUTAL PERIOD STRESS TESTER")
    print("=" * 60)
    print("Testing system survival under brutal market conditions")
    print("Question: How does the system behave when markets try to kill it?")
    print("=" * 60)
    
    tester = BrutalPeriodStressTester()
    
    if args.period == 'all':
        results = tester.run_all_brutal_periods()
    else:
        results = tester.run_brutal_period_test(args.period)
    
    # Save results
    tester.save_stress_test_results(results)
    
    return results

if __name__ == "__main__":
    main()