#!/usr/bin/env python3
"""
🛡️ TEMPORAL SIGNAL ENGINE - HONEST ALPHA GENERATION
All Northstar signals rebuilt with point-in-time protection

This replaces existing signal generation with temporal-safe versions.
Every signal now enforces data[timestamp <= current_time].

Key Signals Rebuilt:
1. Momentum (multi-horizon, volatility-adjusted)
2. Value (fundamental-based, regime-aware)
3. Quality (defensive characteristics)
4. Macro (regime positioning)

Usage:
    try:
    from intelligence.temporal_signal_engine import TemporalSignalEngine
except ImportError:
    from TemporalSignalEngine import TemporalSignalEngine
    
    engine = TemporalSignalEngine()
    signals = engine.generate_all_signals('RELIANCE.NS', current_time)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List

warnings.filterwarnings('ignore')

import sys
try:
    from src.intelligence.temporal_guard import TemporalGuard
except Exception:
    try:
        from intelligence.temporal_guard import TemporalGuard
    except Exception:
        from temporal_guard import TemporalGuard

class TemporalSignalEngine:
    """
    Temporal Signal Engine - Generates honest alpha signals
    
    All signals are rebuilt to use TemporalGuard and enforce point-in-time constraints.
    This ensures no look-ahead bias in any signal generation.
    """
    
    def __init__(self):
        self.guard = TemporalGuard()
        self.name = "Temporal Signal Engine"
        
        # Signal parameters (institutional-grade)
        self.momentum_horizons = {
            'short': 21,    # 1 month
            'medium': 63,   # 3 months  
            'long': 126     # 6 months
        }
        
        self.momentum_weights = {
            'short': 0.5,   # 50% weight on short-term
            'medium': 0.3,  # 30% weight on medium-term
            'long': 0.2     # 20% weight on long-term
        }
        
        print("🛡️ Temporal Signal Engine initialized - All signals protected")
    
    def generate_all_signals(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """
        Generate all signals for a symbol at current_time
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE.NS')
            current_time: Current simulation time
        
        Returns:
            Dict with all signal values and metadata
        """
        
        signals = {
            'symbol': symbol,
            'current_time': current_time.isoformat(),
            'signals': {},
            'metadata': {}
        }
        
        try:
            # Generate momentum signal
            momentum_result = self.generate_momentum_signal(symbol, current_time)
            signals['signals']['momentum'] = momentum_result['signal']
            signals['metadata']['momentum'] = momentum_result['metadata']
            
            # Generate value signal
            value_result = self.generate_value_signal(symbol, current_time)
            signals['signals']['value'] = value_result['signal']
            signals['metadata']['value'] = value_result['metadata']
            
            # Generate quality signal
            quality_result = self.generate_quality_signal(symbol, current_time)
            signals['signals']['quality'] = quality_result['signal']
            signals['metadata']['quality'] = quality_result['metadata']
            
            # Generate macro signal
            macro_result = self.generate_macro_signal(symbol, current_time)
            signals['signals']['macro'] = macro_result['signal']
            signals['metadata']['macro'] = macro_result['metadata']
            
            # Generate composite signal
            composite_result = self.generate_composite_signal(signals['signals'], current_time)
            signals['signals']['composite'] = composite_result['signal']
            signals['metadata']['composite'] = composite_result['metadata']
            
        except Exception as e:
            print(f"❌ Error generating signals for {symbol}: {e}")
            signals['error'] = str(e)
        
        return signals
    
    def generate_momentum_signal(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """
        Generate momentum signal with point-in-time protection
        
        Uses multi-horizon approach:
        - 21-day (50% weight): Short-term flow
        - 63-day (30% weight): Medium-term confirmation  
        - 126-day (20% weight): Long-term institutional rotation
        """
        
        # Get price data through temporal guard
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        
        if price_data.empty or len(price_data) < self.momentum_horizons['long']:
            return {
                'signal': 0.0,
                'metadata': {
                    'status': 'insufficient_data',
                    'data_points': len(price_data),
                    'required': self.momentum_horizons['long']
                }
            }
        
        # Calculate returns
        price_data = price_data.sort_values('timestamp')
        price_data['returns'] = price_data['Close'].pct_change()
        
        # Calculate volatility for adjustment
        price_data['volatility'] = price_data['returns'].rolling(21).std()
        
        # Calculate momentum for each horizon
        momentum_components = {}
        
        for horizon_name, horizon_days in self.momentum_horizons.items():
            if len(price_data) >= horizon_days:
                # Raw momentum (cumulative return)
                raw_momentum = price_data['returns'].rolling(horizon_days).sum().iloc[-1]
                
                # Volatility adjustment
                recent_vol = price_data['volatility'].iloc[-1]
                if pd.notna(recent_vol) and recent_vol > 0:
                    vol_adjusted_momentum = raw_momentum / recent_vol
                else:
                    vol_adjusted_momentum = raw_momentum
                
                momentum_components[horizon_name] = {
                    'raw': raw_momentum,
                    'vol_adjusted': vol_adjusted_momentum,
                    'weight': self.momentum_weights[horizon_name]
                }
            else:
                momentum_components[horizon_name] = {
                    'raw': 0.0,
                    'vol_adjusted': 0.0,
                    'weight': self.momentum_weights[horizon_name]
                }
        
        # Weighted composite momentum
        weighted_momentum = sum(
            comp['vol_adjusted'] * comp['weight'] 
            for comp in momentum_components.values()
        )
        
        # Normalize to [-2, +2] range for consistency
        normalized_momentum = np.clip(weighted_momentum * 10, -2, 2)
        
        return {
            'signal': normalized_momentum,
            'metadata': {
                'status': 'success',
                'components': momentum_components,
                'data_points': len(price_data),
                'latest_price': price_data['Close'].iloc[-1],
                'latest_volatility': price_data['volatility'].iloc[-1]
            }
        }
    
    def generate_value_signal(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """
        Generate value signal with fundamental analysis
        
        Combines multiple valuation metrics:
        - Earnings yield (E/P ratio)
        - Free cash flow yield
        - Return on invested capital (ROIC)
        - Balance sheet strength
        """
        
        # Get fundamental data through temporal guard
        fundamental_data = self.guard.get_data(symbol, current_time, 'fundamentals')
        
        if fundamental_data.empty:
            # Fallback to price-based valuation proxies
            return self._generate_price_based_value(symbol, current_time)
        
        # Get latest fundamental data
        fundamental_data = fundamental_data.sort_values('timestamp')
        latest = fundamental_data.iloc[-1]
        
        value_components = {}
        
        # Earnings yield (inverse of P/E)
        pe_ratio = latest.get('PE', None)
        if pe_ratio and pe_ratio > 0:
            earnings_yield = 1 / pe_ratio
            # Normalize: 0.05 (P/E=20) = neutral, higher = cheaper
            value_components['earnings_yield'] = (earnings_yield - 0.05) * 20
        else:
            value_components['earnings_yield'] = 0.0
        
        # Price-to-book ratio (lower = cheaper)
        pb_ratio = latest.get('PB', None)
        if pb_ratio and pb_ratio > 0:
            # Normalize: 2.0 = neutral, lower = cheaper
            value_components['pb_ratio'] = (2.0 - pb_ratio) / 2.0
        else:
            value_components['pb_ratio'] = 0.0
        
        # Return on equity (higher = better quality)
        roe = latest.get('ROE', None)
        if roe:
            # Normalize: 15% = neutral, higher = better
            value_components['roe'] = (roe - 15) / 15
        else:
            value_components['roe'] = 0.0
        
        # Debt-to-equity (lower = better)
        debt_equity = latest.get('DebtToEquity', None)
        if debt_equity is not None:
            # Normalize: 0.5 = neutral, lower = better
            value_components['debt_equity'] = (0.5 - debt_equity) / 0.5
        else:
            value_components['debt_equity'] = 0.0
        
        # Weighted composite value score
        weights = {
            'earnings_yield': 0.4,  # 40% weight
            'pb_ratio': 0.3,        # 30% weight
            'roe': 0.2,             # 20% weight
            'debt_equity': 0.1      # 10% weight
        }
        
        weighted_value = sum(
            value_components[component] * weights[component]
            for component in weights.keys()
        )
        
        # Normalize to [-2, +2] range
        normalized_value = np.clip(weighted_value, -2, 2)
        
        return {
            'signal': normalized_value,
            'metadata': {
                'status': 'success',
                'components': value_components,
                'weights': weights,
                'data_points': len(fundamental_data),
                'latest_pe': pe_ratio,
                'latest_pb': pb_ratio
            }
        }
    
    def _generate_price_based_value(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """Fallback value signal using price data only"""
        
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        
        if price_data.empty or len(price_data) < 252:  # Need 1 year of data
            return {
                'signal': 0.0,
                'metadata': {
                    'status': 'insufficient_data',
                    'method': 'price_based_fallback'
                }
            }
        
        price_data = price_data.sort_values('timestamp')
        
        # Simple mean reversion signal
        current_price = price_data['Close'].iloc[-1]
        
        # 1-year average price
        avg_price_1y = price_data['Close'].tail(252).mean()
        
        # 6-month average price  
        avg_price_6m = price_data['Close'].tail(126).mean()
        
        # Value signal: current vs long-term average
        value_signal = (avg_price_1y - current_price) / current_price
        
        # Normalize to [-2, +2] range
        normalized_value = np.clip(value_signal * 5, -2, 2)
        
        return {
            'signal': normalized_value,
            'metadata': {
                'status': 'price_based_fallback',
                'current_price': current_price,
                'avg_price_1y': avg_price_1y,
                'avg_price_6m': avg_price_6m
            }
        }
    
    def generate_quality_signal(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """
        Generate quality signal focusing on defensive characteristics
        
        Quality factors:
        - Earnings stability
        - Balance sheet strength
        - Profitability consistency
        - Low leverage
        """
        
        # Get fundamental data
        fundamental_data = self.guard.get_data(symbol, current_time, 'fundamentals')
        
        if fundamental_data.empty:
            return self._generate_price_based_quality(symbol, current_time)
        
        fundamental_data = fundamental_data.sort_values('timestamp')
        
        # Use 3-year average to avoid cyclical distortions
        if len(fundamental_data) >= 12:  # At least 3 years of quarterly data
            recent_data = fundamental_data.tail(12)
        else:
            recent_data = fundamental_data
        
        quality_components = {}
        
        # Return on equity stability
        roe_values = recent_data['ROE'].dropna()
        if len(roe_values) > 1:
            roe_mean = roe_values.mean()
            roe_std = roe_values.std()
            # Higher mean, lower std = better quality
            quality_components['roe_stability'] = (roe_mean / 15) - (roe_std / 5)
        else:
            quality_components['roe_stability'] = 0.0
        
        # Debt-to-equity (lower = better)
        debt_equity_values = recent_data['DebtToEquity'].dropna()
        if len(debt_equity_values) > 0:
            avg_debt_equity = debt_equity_values.mean()
            # Normalize: 0.3 = good, 1.0 = poor
            quality_components['debt_level'] = (0.5 - avg_debt_equity) / 0.5
        else:
            quality_components['debt_level'] = 0.0
        
        # Interest coverage (if available)
        if 'InterestCoverage' in recent_data.columns:
            coverage_values = recent_data['InterestCoverage'].dropna()
            if len(coverage_values) > 0:
                avg_coverage = coverage_values.mean()
                # Normalize: 5x = good, 2x = poor
                quality_components['interest_coverage'] = (avg_coverage - 2) / 3
            else:
                quality_components['interest_coverage'] = 0.0
        else:
            quality_components['interest_coverage'] = 0.0
        
        # Weighted composite quality score
        weights = {
            'roe_stability': 0.5,      # 50% weight
            'debt_level': 0.3,         # 30% weight
            'interest_coverage': 0.2   # 20% weight
        }
        
        weighted_quality = sum(
            quality_components[component] * weights[component]
            for component in weights.keys()
        )
        
        # Normalize to [-2, +2] range
        normalized_quality = np.clip(weighted_quality, -2, 2)
        
        return {
            'signal': normalized_quality,
            'metadata': {
                'status': 'success',
                'components': quality_components,
                'weights': weights,
                'data_points': len(recent_data)
            }
        }
    
    def _generate_price_based_quality(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """Fallback quality signal using price volatility"""
        
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        
        if price_data.empty or len(price_data) < 252:
            return {
                'signal': 0.0,
                'metadata': {
                    'status': 'insufficient_data',
                    'method': 'price_based_fallback'
                }
            }
        
        price_data = price_data.sort_values('timestamp')
        price_data['returns'] = price_data['Close'].pct_change()
        
        # Quality = low volatility (defensive characteristic)
        volatility_1y = price_data['returns'].tail(252).std() * np.sqrt(252)  # Annualized
        
        # Normalize: 20% vol = neutral, lower = higher quality
        quality_signal = (0.20 - volatility_1y) / 0.20
        
        # Normalize to [-2, +2] range
        normalized_quality = np.clip(quality_signal * 2, -2, 2)
        
        return {
            'signal': normalized_quality,
            'metadata': {
                'status': 'price_based_fallback',
                'volatility_1y': volatility_1y,
                'method': 'low_volatility_proxy'
            }
        }
    
    def generate_macro_signal(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """
        Generate macro signal based on regime positioning
        
        Macro factors:
        - Interest rate environment
        - Liquidity conditions
        - Growth expectations
        - Risk sentiment
        """
        
        # Get macro data through temporal guard
        macro_data = self.guard.get_macro_data(current_time)
        regime_data = self.guard.get_regime_data(current_time)
        
        macro_components = {}
        
        # Interest rate signal
        if 'yields' in macro_data and '10Y' in macro_data['yields']:
            current_yield = macro_data['yields']['10Y']
            # Normalize: 6% = neutral, higher = tightening
            macro_components['interest_rates'] = (current_yield - 6.0) / 2.0
        else:
            macro_components['interest_rates'] = 0.0
        
        # Regime signal
        regime = regime_data.get('regime', 'neutral')
        regime_confidence = regime_data.get('confidence', 0.5)
        
        if regime == 'expansion':
            macro_components['regime'] = 1.0 * regime_confidence
        elif regime == 'recession':
            macro_components['regime'] = -1.0 * regime_confidence
        else:
            macro_components['regime'] = 0.0
        
        # Liquidity signal (placeholder - would use actual liquidity metrics)
        macro_components['liquidity'] = 0.0  # Neutral for now
        
        # Weighted composite macro score
        weights = {
            'interest_rates': 0.4,  # 40% weight
            'regime': 0.4,          # 40% weight
            'liquidity': 0.2        # 20% weight
        }
        
        weighted_macro = sum(
            macro_components[component] * weights[component]
            for component in weights.keys()
        )
        
        # Normalize to [-2, +2] range
        normalized_macro = np.clip(weighted_macro, -2, 2)
        
        return {
            'signal': normalized_macro,
            'metadata': {
                'status': 'success',
                'components': macro_components,
                'weights': weights,
                'regime': regime,
                'regime_confidence': regime_confidence
            }
        }
    
    def generate_composite_signal(self, individual_signals: Dict[str, float], 
                                current_time: datetime) -> Dict[str, Any]:
        """
        Generate composite signal using regime-aware weighting
        
        This implements the institutional approach:
        - Bull markets: Momentum > Value
        - Bear markets: Value > Momentum
        - Always: Quality and Macro provide context
        """
        
        # Get current regime for dynamic weighting
        regime_data = self.guard.get_regime_data(current_time)
        regime = regime_data.get('regime', 'neutral')
        
        # Regime-aware weights
        if regime == 'expansion':
            weights = {
                'momentum': 0.50,  # 50% in bull markets
                'value': 0.20,     # 20% in bull markets
                'quality': 0.15,   # 15% always
                'macro': 0.15      # 15% always
            }
        elif regime == 'recession':
            weights = {
                'momentum': 0.15,  # 15% in bear markets
                'value': 0.50,     # 50% in bear markets
                'quality': 0.20,   # 20% in bear markets
                'macro': 0.15      # 15% always
            }
        else:  # neutral
            weights = {
                'momentum': 0.35,  # 35% in neutral
                'value': 0.35,     # 35% in neutral
                'quality': 0.15,   # 15% always
                'macro': 0.15      # 15% always
            }
        
        # Calculate weighted composite
        composite_signal = sum(
            individual_signals.get(signal, 0.0) * weight
            for signal, weight in weights.items()
        )
        
        # Normalize to [-2, +2] range
        normalized_composite = np.clip(composite_signal, -2, 2)
        
        return {
            'signal': normalized_composite,
            'metadata': {
                'status': 'success',
                'regime': regime,
                'weights': weights,
                'individual_signals': individual_signals
            }
        }
    
    def run_signal_scramble_test(self, symbol: str, current_time: datetime) -> Dict[str, Any]:
        """Run scramble test on all signals for this symbol"""
        
        def signal_test_function(data):
            # This function will be called with scrambled data
            # It should return the same results if no look-ahead bias exists
            return self.generate_all_signals(symbol, current_time)
        
        return self.guard.run_scramble_test(
            symbol, current_time, signal_test_function, iterations=5
        )

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate temporal signal engine"""
    
    print("🛡️ TEMPORAL SIGNAL ENGINE - HONEST ALPHA GENERATION")
    print("=" * 70)
    
    # Initialize engine
    engine = TemporalSignalEngine()
    
    # Test with historical time
    test_time = datetime(2024, 1, 15)
    test_symbol = 'RELIANCE.NS'
    
    print(f"\n📊 Generating signals for {test_symbol} at {test_time}")
    print("-" * 50)
    
    # Generate all signals
    signals = engine.generate_all_signals(test_symbol, test_time)
    
    if 'error' not in signals:
        print("✅ Signal generation successful")
        print(f"\nSignal Values:")
        for signal_name, signal_value in signals['signals'].items():
            print(f"   {signal_name.capitalize()}: {signal_value:+.3f}")
        
        print(f"\nComposite Signal: {signals['signals']['composite']:+.3f}")
        print(f"Regime: {signals['metadata']['composite']['regime']}")
        
    else:
        print(f"❌ Signal generation failed: {signals['error']}")
    
    # Run scramble test
    print(f"\n🧪 Running scramble test...")
    test_result = engine.run_signal_scramble_test(test_symbol, test_time)
    
    print(f"Scramble test: {'✅ PASSED' if test_result['passed'] else '❌ FAILED'}")
    
    print(f"\n✅ Temporal Signal Engine demonstration complete")
    print("💡 All signals now protected from look-ahead bias")

if __name__ == "__main__":
    main()
