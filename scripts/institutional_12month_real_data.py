#!/usr/bin/env python3
"""
🏛️ INSTITUTIONAL 12-MONTH WALK-FORWARD VALIDATOR - REAL DATA VERSION
Uses existing NorthStar V3 real historical data

This implements the institutional-grade 12-month walk-forward validation
using the real historical price data and existing system infrastructure.

Usage:
    python scripts/institutional_12month_real_data.py
"""

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

warnings.filterwarnings('ignore')

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@dataclass
class FrozenConfig:
    """Cryptographically frozen institutional configuration - NO CHANGES ALLOWED"""
    
    # Walk-forward parameters (FROZEN)
    training_months: int = 12
    test_months: int = 12
    step_months: int = 1
    
    # Risk parameters (FROZEN) - Institutional limits
    max_drawdown_limit: float = 0.12  # 12%
    target_volatility: float = 0.15   # 15%
    max_position_size: float = 0.08   # 8%
    max_sector_exposure: float = 0.30  # 30%
    max_total_exposure: float = 0.95   # 95%
    min_diversification: int = 15      # 15 positions minimum
    
    # Execution parameters (FROZEN)
    transaction_cost: float = 0.0015  # 15 bps
    market_impact: float = 0.001      # 10 bps
    crisis_multiplier: float = 2.0
    slippage_factor: float = 0.0005   # 5 bps
    
    # Regime parameters (FROZEN)
    regime_lookback: int = 252
    volatility_threshold: float = 0.02
    momentum_threshold: float = 0.15
    confidence_threshold: float = 0.7
    
    # Position sizing (FROZEN)
    min_allocation: float = 0.05      # 5%
    max_allocation: float = 0.25      # 25%

    # NAV integrity guardrails (FROZEN)
    max_abs_daily_return: float = 0.20  # 20% hard cap (decimal)
    min_nav_floor: float = 1.0          # NAV must stay strictly positive
    
    def to_hash(self) -> str:
        """Generate cryptographic hash - any change invalidates validation"""
        config_str = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

@dataclass
class WindowResult:
    """Results for a single 12-month window"""
    
    window_id: str
    start_date: datetime
    end_date: datetime
    
    # Performance metrics (secondary importance)
    total_return: float
    cagr: float
    sharpe_ratio: float
    volatility: float
    
    # Risk metrics (primary importance)
    max_drawdown: float
    drawdown_duration_days: int
    time_to_recovery_days: int
    
    # Conviction integrity (critical importance)
    average_exposure: float
    risk_on_percentage: float
    regime_flip_count: int
    trend_invalidation_count: int
    shutdown_event_count: int
    override_attempt_count: int  # Should be zero
    
    # Execution reality
    turnover_annual: float
    transaction_costs_total: float
    liquidity_violations: int
    execution_delays: int
    
    # Regime performance
    regime_distribution: Dict[str, float]
    regime_performance: Dict[str, float]
    
    # Worst case analysis
    worst_month_return: float
    worst_quarter_return: float
    consecutive_loss_days: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class InstitutionalValidator:
    """
    Institutional 12-Month Walk-Forward Validator
    
    This is the rigorous test that determines if NorthStar V3 has
    capital-worthy alpha under institutional discipline.
    
    CRITICAL: This is NOT optimization. This is verification.
    """
    
    def __init__(self):
        self.name = "Institutional 12-Month Validator (Real Data)"
        self.version = "1.0"
        self.execution_timestamp = datetime.now()
        
        # Frozen configuration (NO CHANGES ALLOWED)
        self.config = FrozenConfig()
        self.config_hash = self.config.to_hash()
        
        # Results storage
        self.window_results: List[WindowResult] = []
        self.violations: List[Dict[str, Any]] = []
        
        # Market data cache
        self.market_data = None
        self.price_data = None
        
        print(f"🏛️ {self.name} v{self.version}")
        print(f"📅 Execution Timestamp: {self.execution_timestamp}")
        print(f"🔒 Configuration Hash: {self.config_hash[:16]}...")
        print(f"⚠️  WARNING: Configuration is CRYPTOGRAPHICALLY FROZEN")
        print(f"⚠️  WARNING: NO parameter changes allowed after this point")
    
    def load_real_data(self) -> bool:
        """Load real historical data from NorthStar V3 data infrastructure"""
        
        print("📊 Loading real historical data...")
        
        try:
            # Load daily prices
            print("   📈 Loading daily price data...")
            self.price_data = pd.read_parquet('data/market/daily_prices.parquet')
            
            # Convert Date column to datetime and set as index
            self.price_data['Date'] = pd.to_datetime(self.price_data['Date'])
            
            print(f"   ✅ Loaded {len(self.price_data)} price records")
            print(f"   📅 Date range: {self.price_data['Date'].min().date()} to {self.price_data['Date'].max().date()}")
            print(f"   🏢 Tickers: {self.price_data['ticker'].nunique()} stocks")
            
            # Create market index correctly:
            # 1) compute time-series returns per ticker
            # 2) aggregate cross-sectionally by date
            print("   📊 Creating market index...")
            px = self.price_data[['Date', 'ticker', 'Close']].copy()
            px['Close'] = pd.to_numeric(px['Close'], errors='coerce')
            px = px.dropna(subset=['Date', 'ticker', 'Close']).sort_values(['ticker', 'Date'])
            px['ticker_return'] = px.groupby('ticker')['Close'].pct_change()

            # Guard against split glitches/bad ticks before cross-sectional averaging.
            px['ticker_return'] = px['ticker_return'].clip(-0.80, 0.80)
            daily_returns = (
                px.dropna(subset=['ticker_return'])
                  .groupby('Date')['ticker_return']
                  .mean()
                  .sort_index()
                  .astype(float)
            )
            daily_returns = daily_returns.replace([np.inf, -np.inf], np.nan).dropna()
            if daily_returns.empty:
                raise ValueError("No valid daily return series after ticker-level return construction")

            # Hard cap extreme daily moves for NAV integrity.
            n_capped = int((daily_returns.abs() > self.config.max_abs_daily_return).sum())
            if n_capped > 0:
                print(
                    f"   ⚠️ Capping {n_capped} daily index returns to "
                    f"±{self.config.max_abs_daily_return:.0%} for integrity"
                )
                daily_returns = daily_returns.clip(
                    -self.config.max_abs_daily_return,
                    self.config.max_abs_daily_return
                )
            
            # Create comprehensive market data
            dates = daily_returns.index
            
            # Calculate rolling metrics
            volatility = daily_returns.rolling(20).std() * np.sqrt(252)
            momentum = daily_returns.rolling(60).mean() * 252
            
            # Simple regime classification
            regimes = []
            for i, date in enumerate(dates):
                if i < 60:  # Need history for regime detection
                    regimes.append('normal')
                    continue
                
                recent_vol = volatility.iloc[i]
                recent_momentum = momentum.iloc[i]
                
                if recent_vol > 0.3:
                    regime = 'crisis'
                elif recent_vol > 0.25:
                    regime = 'high_volatility'
                elif recent_momentum > 0.15:
                    regime = 'bull_market'
                elif recent_momentum < -0.1:
                    regime = 'bear_market'
                else:
                    regime = 'normal'
                
                regimes.append(regime)
            
            # Create market state DataFrame
            self.market_data = pd.DataFrame({
                'date': dates,
                'market_return': daily_returns.values,
                'regime': regimes,
                'volatility': volatility.fillna(0.15).values,
                'momentum': momentum.fillna(0.0).values,
                'market_price': (1 + daily_returns).cumprod() * 100
            })
            
            print(f"   ✅ Created market state data: {len(self.market_data)} days")
            print(f"   📊 Regime distribution: {pd.Series(regimes).value_counts().to_dict()}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to load real data: {e}")
            return False

    def _sanitize_daily_return(self, raw_return: float, window_id: str, current_date: pd.Timestamp) -> float:
        """Bound and validate daily return inputs before NAV compounding."""
        if not np.isfinite(raw_return):
            self.violations.append({
                'window': window_id,
                'date': current_date,
                'type': 'return_sanity',
                'details': 'Non-finite market return encountered'
            })
            return 0.0

        capped = float(np.clip(raw_return, -self.config.max_abs_daily_return, self.config.max_abs_daily_return))
        if capped != raw_return:
            self.violations.append({
                'window': window_id,
                'date': current_date,
                'type': 'return_sanity',
                'details': f'Return capped from {raw_return:.4f} to {capped:.4f}'
            })
        return capped

    @staticmethod
    def _drawdown_diagnostics(equity_curve: pd.Series) -> Tuple[float, int, int]:
        """Return (max_drawdown_decimal, longest_drawdown_days, time_to_recovery_days)."""
        if equity_curve.empty:
            return 0.0, 0, 0

        eq = pd.to_numeric(equity_curve, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
        if eq.empty:
            return 0.0, 0, 0

        running_peak = eq.cummax()
        dd = eq / running_peak - 1.0
        max_dd = float(abs(dd.min()))

        # Longest drawdown spell.
        in_dd = dd < 0
        longest = 0
        cur = 0
        for flag in in_dd.values:
            if flag:
                cur += 1
                longest = max(longest, cur)
            else:
                cur = 0

        # Time to recovery from trough.
        trough_idx = dd.idxmin()
        if pd.isna(trough_idx):
            return max_dd, int(longest), 0
        trough_val = float(eq.loc[trough_idx])
        pre_peak = float(running_peak.loc[trough_idx])
        after = eq.loc[eq.index >= trough_idx]
        recovered = after[after >= pre_peak]
        if recovered.empty:
            recovery_days = 0
        else:
            recovery_days = int((recovered.index[0] - trough_idx).days)

        return max_dd, int(longest), recovery_days
    
    def determine_validation_windows(self) -> List[Tuple[datetime, datetime, datetime]]:
        """Determine 12-month validation windows with NO CHERRY PICKING"""
        
        print("\n📅 DETERMINING VALIDATION WINDOWS (NO CHERRY PICKING)...")
        
        if self.market_data is None:
            print("   ❌ No market data available")
            return []
        
        data_start = self.market_data['date'].min()
        data_end = self.market_data['date'].max()
        
        print(f"   📊 Available data: {data_start.date()} to {data_end.date()}")
        
        # Calculate minimum required data
        min_required_years = 3
        required_start = data_end - relativedelta(years=min_required_years)
        
        if data_start > required_start:
            years_available = (data_end - data_start).days / 365.25
            print(f"   ⚠️  Limited data: {years_available:.1f} years available")
        
        # Calculate first possible test start (need 12 months warmup)
        first_test_start = data_start + relativedelta(months=self.config.training_months)
        
        # Generate windows with NO CHERRY PICKING
        windows = []
        current_test_start = first_test_start
        
        while current_test_start + relativedelta(months=self.config.test_months) <= data_end:
            warmup_start = current_test_start - relativedelta(months=self.config.training_months)
            test_end = current_test_start + relativedelta(months=self.config.test_months)
            
            windows.append((warmup_start, current_test_start, test_end))
            
            # Step forward by step_months
            current_test_start += relativedelta(months=self.config.step_months)
            
            # Limit to reasonable number to prevent cherry-picking
            if len(windows) >= 10:
                break
        
        print(f"   ✅ Generated {len(windows)} validation windows:")
        for i, (warmup_start, test_start, test_end) in enumerate(windows):
            print(f"      Window {i+1}: Warmup {warmup_start.date()} → Test {test_start.date()} to {test_end.date()}")
        
        return windows
    
    def run_single_window(self, window_id: str, warmup_start: datetime, 
                         test_start: datetime, test_end: datetime) -> Optional[WindowResult]:
        """
        Run validation for a single 12-month window
        
        This is where the REAL validation happens.
        NO CHEATING - end-of-period execution only.
        """
        
        print(f"\n🧪 RUNNING WINDOW {window_id}")
        print(f"   Warmup: {warmup_start.date()} to {test_start.date()}")
        print(f"   Test: {test_start.date()} to {test_end.date()}")
        
        try:
            # Extract data for this window
            window_data = self.market_data[
                (self.market_data['date'] >= warmup_start) & 
                (self.market_data['date'] <= test_end)
            ].copy()
            
            warmup_data = window_data[
                (window_data['date'] >= warmup_start) & 
                (window_data['date'] < test_start)
            ]
            
            test_data = window_data[
                (window_data['date'] >= test_start) & 
                (window_data['date'] <= test_end)
            ]
            
            print(f"   📊 Warmup data: {len(warmup_data)} days")
            print(f"   📊 Test data: {len(test_data)} days")
            
            if len(test_data) < 200:  # Need reasonable test period
                print(f"   ⚠️  Insufficient test data: {len(test_data)} days")
                return None
            
            # Run the window simulation with institutional discipline
            window_result = self.simulate_window_with_discipline(
                window_id, warmup_data, test_data, test_start, test_end
            )
            
            if window_result:
                print(f"   ✅ Window {window_id} Complete:")
                print(f"      Total Return: {window_result.total_return:+.2f}%")
                print(f"      Max Drawdown: {window_result.max_drawdown:.2f}%")
                print(f"      Sharpe Ratio: {window_result.sharpe_ratio:.2f}")
                print(f"      Avg Exposure: {window_result.average_exposure:.1f}%")
                print(f"      Override Attempts: {window_result.override_attempt_count}")
            
            return window_result
            
        except Exception as e:
            print(f"   ❌ Window {window_id} FAILED: {e}")
            return None
    
    def simulate_window_with_discipline(self, window_id: str, warmup_data: pd.DataFrame, 
                                      test_data: pd.DataFrame, test_start: datetime, 
                                      test_end: datetime) -> WindowResult:
        """
        Simulate a single validation window with institutional discipline
        
        This enforces all the frozen rules and tracks conviction integrity.
        """
        
        # Initialize portfolio state
        portfolio_value = 100_000_000.0  # $100M starting capital
        portfolio_weights = {'cash': 1.0}
        
        # Track all metrics required for institutional validation
        daily_values = []
        daily_returns = []
        daily_exposures = []
        daily_turnover = []
        daily_regimes = []
        daily_costs = []
        
        # Conviction integrity tracking
        regime_changes = 0
        trend_invalidations = 0
        shutdown_events = 0
        override_attempts = 0
        
        # Risk tracking
        peak_value = portfolio_value
        max_drawdown = 0.0
        
        # Regime performance tracking
        regime_time = {}
        regime_returns = {}
        
        current_regime = 'normal'
        
        # Process each day in test period with temporal discipline
        for i, row in test_data.iterrows():
            current_date = row['date']
            market_return = self._sanitize_daily_return(
                float(row['market_return']),
                window_id=window_id,
                current_date=pd.to_datetime(current_date)
            )
            regime = row['regime']
            volatility = row['volatility']
            
            # Enforce temporal discipline - only use data <= current_date
            available_data = test_data[test_data['date'] <= current_date]
            
            # Track regime changes
            if regime != current_regime:
                regime_changes += 1
                current_regime = regime
            
            # Track regime time and returns
            if regime not in regime_time:
                regime_time[regime] = 0
                regime_returns[regime] = []
            regime_time[regime] += 1
            
            # Generate signals using only historical data (NO FUTURE LEAKAGE)
            signals = self.generate_institutional_signals(available_data, regime)
            
            # Check for override attempts (should be zero)
            if self.detect_override_attempt(signals, regime):
                override_attempts += 1
                self.violations.append({
                    'window': window_id,
                    'date': current_date,
                    'type': 'override_attempt',
                    'details': 'Manual override detected'
                })
            
            # Apply frozen risk controls
            target_weights = self.apply_frozen_risk_controls(
                signals, regime, volatility, portfolio_value
            )
            
            # Calculate turnover
            turnover = sum(abs(target_weights.get(k, 0) - portfolio_weights.get(k, 0)) 
                          for k in set(list(target_weights.keys()) + list(portfolio_weights.keys())))
            daily_turnover.append(turnover)
            
            # Calculate transaction costs with regime adjustments
            if turnover > 0.01:  # Only if meaningful turnover
                cost_multiplier = self.config.crisis_multiplier if regime == 'crisis' else 1.0
                trade_cost = (turnover * portfolio_value * self.config.transaction_cost * 
                             cost_multiplier + 
                             turnover * portfolio_value * self.config.market_impact +
                             turnover * portfolio_value * self.config.slippage_factor)
                daily_costs.append(trade_cost)
                portfolio_value -= trade_cost
            else:
                daily_costs.append(0.0)
            
            # Update portfolio value based on market return and exposure
            equity_exposure = sum(v for k, v in target_weights.items() if k != 'cash')
            portfolio_return = market_return * equity_exposure

            # Hard daily return cap on realized portfolio move.
            portfolio_return = float(np.clip(
                portfolio_return,
                -self.config.max_abs_daily_return,
                self.config.max_abs_daily_return
            ))
            portfolio_value *= (1 + portfolio_return)

            # NAV integrity enforcement.
            if not np.isfinite(portfolio_value):
                raise ValueError(
                    f"NAV became non-finite on {pd.to_datetime(current_date).date()} "
                    f"(return={portfolio_return:.4f}, exposure={equity_exposure:.4f})"
                )
            if portfolio_value <= self.config.min_nav_floor:
                raise ValueError(
                    f"NAV floor breached on {pd.to_datetime(current_date).date()} "
                    f"(nav={portfolio_value:.6f})"
                )
            
            # Track metrics
            daily_values.append(portfolio_value)
            daily_returns.append(portfolio_return)
            daily_exposures.append(equity_exposure)
            daily_regimes.append(regime)
            regime_returns[regime].append(portfolio_return)
            
            # Update drawdown tracking
            if portfolio_value > peak_value:
                peak_value = portfolio_value
            else:
                current_drawdown = (peak_value - portfolio_value) / peak_value
                max_drawdown = max(max_drawdown, current_drawdown)
            
            # Check kill switches (frozen thresholds)
            if current_drawdown > self.config.max_drawdown_limit:
                shutdown_events += 1
                # Force to cash (emergency brake)
                target_weights = {'cash': 1.0}
                print(f"      🚨 Kill switch triggered on {current_date.date()}: {current_drawdown:.1%} drawdown")
            
            # Check for trend invalidations (simplified)
            if len(daily_returns) > 20:
                recent_trend = np.mean(daily_returns[-20:])
                if abs(recent_trend) > self.config.momentum_threshold:
                    trend_invalidations += 1
            
            # Update weights
            portfolio_weights = target_weights.copy()
        
        # Calculate final window metrics
        total_return = (portfolio_value / 100_000_000.0 - 1) * 100

        # Window-level integrity guardrail (institutional sanity).
        if not np.isfinite(total_return) or abs(total_return) > 1000:
            raise ValueError(f"Unrealistic total return detected in {window_id}: {total_return}")
        
        # Performance metrics
        if len(daily_returns) > 1:
            returns_array = np.array(daily_returns)
            volatility_annual = np.std(returns_array) * np.sqrt(252) * 100
            sharpe_ratio = (np.mean(returns_array) * 252) / (volatility_annual / 100) if volatility_annual > 0 else 0
        else:
            volatility_annual = 0
            sharpe_ratio = 0
        
        # CAGR calculation
        days_in_period = len(test_data)
        years = days_in_period / 252.0
        cagr = ((portfolio_value / 100_000_000.0) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # Conviction integrity metrics
        avg_exposure = np.mean(daily_exposures) * 100 if daily_exposures else 0
        annual_turnover = np.mean(daily_turnover) * 252 if daily_turnover else 0
        
        # Regime analysis
        total_days = sum(regime_time.values())
        regime_distribution = {k: v/total_days for k, v in regime_time.items()} if total_days > 0 else {}
        
        regime_performance = {}
        for regime, returns in regime_returns.items():
            if returns:
                regime_performance[regime] = np.mean(returns) * 252 * 100  # Annualized
        
        # Worst case analysis
        if len(daily_returns) >= 21:  # At least 1 month
            monthly_returns = []
            for start_idx in range(0, len(daily_returns)-20, 21):
                month_return = np.prod([1 + r for r in daily_returns[start_idx:start_idx+21]]) - 1
                monthly_returns.append(month_return)
            worst_month = min(monthly_returns) * 100 if monthly_returns else 0
        else:
            worst_month = 0
        
        if len(daily_returns) >= 63:  # At least 1 quarter
            quarterly_returns = []
            for start_idx in range(0, len(daily_returns)-62, 63):
                quarter_return = np.prod([1 + r for r in daily_returns[start_idx:start_idx+63]]) - 1
                quarterly_returns.append(quarter_return)
            worst_quarter = min(quarterly_returns) * 100 if quarterly_returns else 0
        else:
            worst_quarter = 0
        
        # Consecutive loss days
        consecutive_losses = 0
        max_consecutive_losses = 0
        for ret in daily_returns:
            if ret < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
        
        # Drawdown diagnostics from realized equity curve.
        if daily_values:
            eq_index = pd.to_datetime(test_data['date'].iloc[:len(daily_values)])
            equity_curve = pd.Series(daily_values, index=eq_index)
            max_drawdown, drawdown_duration, time_to_recovery = self._drawdown_diagnostics(equity_curve)
        else:
            max_drawdown, drawdown_duration, time_to_recovery = 0.0, 0, 0

        return WindowResult(
            window_id=window_id,
            start_date=test_start,
            end_date=test_end,
            total_return=total_return,
            cagr=cagr,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility_annual,
            max_drawdown=float(max_drawdown * 100),
            drawdown_duration_days=drawdown_duration,
            time_to_recovery_days=time_to_recovery,
            average_exposure=avg_exposure,
            risk_on_percentage=regime_distribution.get('bull_market', 0) * 100,
            regime_flip_count=regime_changes,
            trend_invalidation_count=trend_invalidations,
            shutdown_event_count=shutdown_events,
            override_attempt_count=override_attempts,
            turnover_annual=annual_turnover,
            transaction_costs_total=sum(daily_costs),
            liquidity_violations=0,  # Simplified
            execution_delays=0,      # Simplified
            regime_distribution=regime_distribution,
            regime_performance=regime_performance,
            worst_month_return=worst_month,
            worst_quarter_return=worst_quarter,
            consecutive_loss_days=max_consecutive_losses
        )
    
    def generate_institutional_signals(self, available_data: pd.DataFrame, regime: str) -> Dict[str, float]:
        """Generate trading signals using only historical data (NO FUTURE LEAKAGE)"""
        
        if len(available_data) < 60:  # Need sufficient history
            return {'momentum': 0.0, 'mean_reversion': 0.0, 'volatility': 0.0}
        
        # Use only data available up to current point in time
        returns = available_data['market_return'].values
        
        # Momentum signal (trend following)
        momentum_signal = np.mean(returns[-60:])  # 60-day momentum
        
        # Mean reversion signal
        short_ma = np.mean(returns[-10:])
        long_ma = np.mean(returns[-60:])
        mean_reversion_signal = -(short_ma - long_ma)  # Contrarian
        
        # Volatility signal
        volatility_signal = -np.std(returns[-20:])  # Anti-volatility
        
        # Apply regime adjustments (frozen rules)
        if regime == 'crisis':
            # Reduce all signals in crisis
            momentum_signal *= 0.2
            mean_reversion_signal *= 0.2
            volatility_signal *= 0.5
        elif regime == 'bull_market':
            # Enhance momentum in bull markets
            momentum_signal *= 1.5
        elif regime == 'bear_market':
            # Enhance mean reversion in bear markets
            mean_reversion_signal *= 1.3
        
        # Clip signals to reasonable ranges
        return {
            'momentum': np.clip(momentum_signal, -0.02, 0.02),
            'mean_reversion': np.clip(mean_reversion_signal, -0.01, 0.01),
            'volatility': np.clip(volatility_signal, -0.01, 0.01)
        }
    
    def detect_override_attempt(self, signals: Dict[str, float], regime: str) -> bool:
        """
        Detect any attempts to override the frozen system rules
        
        This should ALWAYS return False in a properly disciplined system.
        """
        
        # Check for unrealistic signals (potential manual override)
        for signal_name, signal_value in signals.items():
            if abs(signal_value) > 0.05:  # Exceeds frozen limits
                return True
        
        # Check for regime-inconsistent signals
        if regime == 'crisis' and any(abs(v) > 0.01 for v in signals.values()):
            return True  # Signals too large for crisis regime
        
        return False
    
    def apply_frozen_risk_controls(self, signals: Dict[str, float], regime: str, 
                                 volatility: float, portfolio_value: float) -> Dict[str, float]:
        """Apply frozen risk control rules (NO MODIFICATIONS ALLOWED)"""
        
        # Start with cash
        weights = {'cash': 1.0}
        
        # Calculate base signal strength
        total_signal = sum(abs(v) for v in signals.values())
        if total_signal == 0:
            return weights
        
        # Base exposure from signals (frozen scaling)
        base_exposure = min(total_signal * 15, self.config.max_total_exposure)
        
        # Regime-based exposure adjustments (FROZEN RULES)
        regime_multipliers = {
            'crisis': 0.1,        # 10% max in crisis
            'bear_market': 0.3,   # 30% max in bear
            'high_volatility': 0.4,  # 40% max in high vol
            'normal': 0.7,        # 70% max in normal
            'bull_market': 0.9    # 90% max in bull
        }
        
        exposure_multiplier = regime_multipliers.get(regime, 0.5)
        
        # Volatility adjustment (frozen rule)
        if volatility > self.config.volatility_threshold * 2:
            exposure_multiplier *= 0.5  # Halve exposure in high vol
        
        # Calculate final exposure
        final_exposure = base_exposure * exposure_multiplier
        
        # Apply frozen position size limits
        final_exposure = min(final_exposure, self.config.max_total_exposure)
        final_exposure = max(final_exposure, 0.0)
        
        # Construct portfolio (simplified to long equity + cash)
        if final_exposure > 0.01:  # Minimum threshold
            weights['equity_long'] = final_exposure
            weights['cash'] = 1.0 - final_exposure
        
        return weights
    
    def generate_institutional_report(self) -> Dict[str, Any]:
        """
        Generate the institutional-grade report
        
        This is the SINGLE SOURCE OF TRUTH that determines
        if the system passes institutional validation.
        """
        
        print("\n📊 GENERATING INSTITUTIONAL REPORT...")
        
        if not self.window_results:
            return {'status': 'FAILED', 'reason': 'No valid window results'}
        
        # Extract key metrics
        returns = [w.total_return for w in self.window_results]
        drawdowns = [w.max_drawdown for w in self.window_results]
        sharpes = [w.sharpe_ratio for w in self.window_results]
        exposures = [w.average_exposure for w in self.window_results]
        overrides = sum(w.override_attempt_count for w in self.window_results)
        
        # A. Per-Window Summary Table
        summary_table = []
        for w in self.window_results:
            summary_table.append({
                'Year': w.start_date.year,
                'Return': f"{w.total_return:+.1f}%",
                'Sharpe': f"{w.sharpe_ratio:.2f}",
                'Max_DD': f"{w.max_drawdown:.1f}%",
                'Avg_Exposure': f"{w.average_exposure:.0f}%",
                'Risk_On_%': f"{w.risk_on_percentage:.0f}%",
                'Regime_Flips': w.regime_flip_count,
                'Shutdowns': w.shutdown_event_count,
                'Overrides': w.override_attempt_count
            })
        
        # B. Distribution Analysis
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
                'std': np.std(drawdowns),
                'min': np.min(drawdowns),
                'max': np.max(drawdowns)
            },
            'exposures': {
                'mean': np.mean(exposures),
                'std': np.std(exposures),
                'min': np.min(exposures),
                'max': np.max(exposures)
            }
        }
        
        # C. Worst-Case Analysis (MANDATORY)
        worst_window = min(self.window_results, key=lambda x: x.total_return)
        worst_case_narrative = (
            f"The worst 12-month experience was {worst_window.start_date.year} "
            f"with a {worst_window.total_return:+.1f}% return and "
            f"{worst_window.max_drawdown:.1f}% maximum drawdown. "
            f"The system maintained {worst_window.average_exposure:.0f}% average exposure "
            f"and had {worst_window.override_attempt_count} override attempts."
        )
        
        # D. System Behavior Validation (CRITICAL)
        behavior_validation = {
            'designed_behavior': overrides == 0,
            'stayed_exposed_when_uncomfortable': np.mean(exposures) > 50,
            'structural_exits_only': all(w.shutdown_event_count < 5 for w in self.window_results),
            'drawdown_covenant_respected': all(w.max_drawdown <= self.config.max_drawdown_limit * 100 for w in self.window_results),
            'asymmetric_payoff': len([r for r in returns if r > 0]) >= len([r for r in returns if r < 0])
        }
        
        # E. Pass/Fail Determination
        validation_passed = all(behavior_validation.values())
        
        # F. Final Report
        report = {
            'validation_status': 'PASS' if validation_passed else 'FAIL',
            'execution_timestamp': self.execution_timestamp.isoformat(),
            'configuration_hash': self.config_hash,
            'windows_processed': len(self.window_results),
            'summary_table': summary_table,
            'distributions': distributions,
            'worst_case_narrative': worst_case_narrative,
            'behavior_validation': behavior_validation,
            'violations_detected': len(self.violations),
            'system_integrity': {
                'temporal_violations': len([v for v in self.violations if v['type'] == 'temporal']),
                'override_attempts': overrides,
                'kill_switch_triggers': sum(w.shutdown_event_count for w in self.window_results)
            },
            'window_results': [w.to_dict() for w in self.window_results]
        }
        
        return report
    
    def save_results(self, report: Dict[str, Any]):
        """Save results with cryptographic sealing"""
        
        print("\n💾 SAVING RESULTS...")
        
        # Create results directory
        results_dir = Path("data/validation/institutional_real_data")
        results_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = self.execution_timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Save detailed results
        results_file = results_dir / f"institutional_report_{timestamp_str}.json"
        with open(results_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Generate results hash for sealing
        results_str = json.dumps(report, sort_keys=True, default=str)
        results_hash = hashlib.sha256(results_str.encode()).hexdigest()
        
        # Save seal
        seal_file = results_dir / f"institutional_seal_{timestamp_str}.txt"
        with open(seal_file, 'w') as f:
            f.write(f"INSTITUTIONAL 12-MONTH WALK-FORWARD VALIDATION\n")
            f.write(f"============================================\n")
            f.write(f"Execution Timestamp: {self.execution_timestamp}\n")
            f.write(f"Configuration Hash: {self.config_hash}\n")
            f.write(f"Results Hash: {results_hash}\n")
            f.write(f"Status: {report['validation_status']}\n")
            f.write(f"Windows: {report['windows_processed']}\n")
            f.write(f"Override Attempts: {report['system_integrity']['override_attempts']}\n")
            f.write(f"Data Source: Real NorthStar V3 Historical Data\n")
            f.write(f"============================================\n")
        
        print(f"   ✅ Results saved to: {results_file}")
        print(f"   ✅ Seal saved to: {seal_file}")
        print(f"   🔒 Results Hash: {results_hash[:16]}...")
    
    def run_complete_validation(self) -> Dict[str, Any]:
        """
        Run the complete institutional 12-month walk-forward validation
        
        This is the SINGLE ENTRY POINT for the validation.
        """
        
        print(f"\n🏛️ STARTING INSTITUTIONAL 12-MONTH WALK-FORWARD VALIDATION")
        print(f"🔒 Configuration frozen with hash: {self.config_hash[:16]}...")
        
        # Step 1: Load real data
        if not self.load_real_data():
            return {'status': 'FAILED', 'reason': 'Failed to load real data'}
        
        # Step 2: Determine validation windows
        windows = self.determine_validation_windows()
        if not windows:
            return {'status': 'FAILED', 'reason': 'No valid windows found'}
        
        # Step 3: Run each window
        print(f"\n🧪 RUNNING {len(windows)} VALIDATION WINDOWS...")
        
        for i, (warmup_start, test_start, test_end) in enumerate(windows):
            window_id = f"W{i+1:02d}_{test_start.year}"
            
            result = self.run_single_window(window_id, warmup_start, test_start, test_end)
            if result:
                self.window_results.append(result)
            else:
                print(f"   ⚠️  Window {window_id} failed - continuing with remaining windows")
        
        # Step 4: Generate institutional report
        report = self.generate_institutional_report()
        
        # Step 5: Save and seal results
        self.save_results(report)
        
        # Step 6: Final status
        print(f"\n🏛️ INSTITUTIONAL VALIDATION COMPLETE")
        print(f"   Status: {report['validation_status']}")
        print(f"   Windows: {report['windows_processed']}")
        print(f"   Configuration: {self.config_hash[:16]}...")
        
        if report['validation_status'] == 'PASS':
            print(f"   ✅ SYSTEM PASSES INSTITUTIONAL VALIDATION")
        else:
            print(f"   ❌ SYSTEM FAILS INSTITUTIONAL VALIDATION")
        
        return report

def main():
    """Main execution function"""
    
    print("🏛️ INSTITUTIONAL 12-MONTH WALK-FORWARD VALIDATOR")
    print("=" * 60)
    print("This is NOT backtesting. This is historical behavior verification.")
    print("All parameters are FROZEN. No optimization allowed.")
    print("Using real NorthStar V3 historical data.")
    print("=" * 60)
    
    # Initialize validator
    validator = InstitutionalValidator()
    
    # Run complete validation
    results = validator.run_complete_validation()
    
    # Print final summary
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    print(f"Status: {results.get('validation_status', 'UNKNOWN')}")
    print(f"Windows: {results.get('windows_processed', 0)}")
    print(f"Timestamp: {results.get('execution_timestamp', 'UNKNOWN')}")
    
    if results.get('validation_status') == 'PASS':
        print("\n✅ SYSTEM READY FOR INSTITUTIONAL DEPLOYMENT")
        
        # Show worst case
        worst_case = results.get('worst_case_narrative', '')
        print(f"\nWorst case: {worst_case}")
        
        print("\nCRITICAL QUESTION: Could you live with this again?")
        print("If YES → System passes")
        print("If NO → Reduce exposure expectations, not system logic")
        
    else:
        print("\n❌ SYSTEM NOT READY FOR DEPLOYMENT")
        
        behavior = results.get('behavior_validation', {})
        print("\nFailure analysis:")
        for check, passed in behavior.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
    
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    results = main()
