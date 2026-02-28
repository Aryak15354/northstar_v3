#!/usr/bin/env python3
"""
🎯 REGIME-AWARE SIGNAL SPECIALISTS - LAYER 4
Institutional-grade signal specialists that adapt to market regimes

This implements Layer 4 of the institutional alpha engine:
- Momentum Specialist: Trend-following optimized for bull markets
- Value Specialist: Contrarian strategies for bear markets  
- Quality Specialist: Defensive positioning for uncertain markets
- Macro Specialist: Regime-based sector and factor positioning

Each specialist:
1. Uses temporal protection (Layer 3) for all data access
2. Adapts signal strength based on current market regime
3. Provides cross-sectional rankings with confidence scores
4. Includes regime-specific performance tracking

Usage:
    from src.intelligence.regime_aware_specialists import RegimeAwareSpecialists
    
    specialists = RegimeAwareSpecialists()
    signals = specialists.generate_regime_signals(symbols, current_time)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

warnings.filterwarnings('ignore')

import sys
from src.intelligence.temporal_guard import TemporalGuard

class MarketRegime(Enum):
    """Market regime classifications"""
    EXPANSION = "expansion"      # Bull market - momentum works
    RECESSION = "recession"      # Bear market - value works  
    RECOVERY = "recovery"        # Early cycle - quality + momentum
    SLOWDOWN = "slowdown"        # Late cycle - quality + value
    CRISIS = "crisis"           # Crisis - quality only
    NEUTRAL = "neutral"         # Uncertain - balanced approach

@dataclass
class SpecialistSignal:
    """Signal output from a specialist"""
    symbol: str
    signal_strength: float      # [-2, +2] normalized signal
    confidence: float          # [0, 1] confidence in signal
    regime_fit: float         # [0, 1] how well signal fits current regime
    cross_sectional_rank: float  # [0, 1] percentile rank vs universe
    metadata: Dict[str, Any]   # Additional signal information

@dataclass
class RegimeContext:
    """Current market regime context"""
    regime: MarketRegime
    confidence: float          # [0, 1] confidence in regime classification
    regime_duration: int       # Days in current regime
    transition_probability: Dict[MarketRegime, float]  # Transition probabilities
    macro_indicators: Dict[str, float]  # Supporting macro data

class RegimeDetector:
    """
    Enhanced regime detection with confidence scoring
    
    Uses multiple indicators to classify market regime:
    - VIX levels and term structure
    - Yield curve shape and level
    - Credit spreads
    - Momentum and mean reversion patterns
    - Economic indicators
    """
    
    def __init__(self, guard: TemporalGuard):
        self.guard = guard
        self.regime_history = []
        
        # Regime thresholds (institutional-grade parameters)
        self.vix_thresholds = {
            'low': 15,      # VIX < 15 = complacency
            'normal': 25,   # VIX 15-25 = normal
            'elevated': 35, # VIX 25-35 = stress
            'crisis': 35    # VIX > 35 = crisis
        }
        
        print("🎯 Regime Detector initialized - Enhanced regime classification")
    
    def detect_regime(self, current_time: datetime) -> RegimeContext:
        """Detect current market regime with confidence scoring"""
        
        # Get macro data through temporal guard
        macro_data = self.guard.get_macro_data(current_time)
        
        # Initialize regime scores
        regime_scores = {regime: 0.0 for regime in MarketRegime}
        
        # Analyze yield curve (if available)
        if 'yields' in macro_data:
            yields = macro_data['yields']
            regime_scores.update(self._analyze_yield_curve(yields))
        
        # Analyze market volatility (mock for now)
        vix_level = self._get_vix_proxy(current_time)
        regime_scores.update(self._analyze_volatility(vix_level, regime_scores))
        
        # Analyze momentum patterns
        momentum_signal = self._analyze_market_momentum(current_time)
        regime_scores.update(self._analyze_momentum_patterns(momentum_signal, regime_scores))
        
        # Determine primary regime
        primary_regime = max(regime_scores, key=regime_scores.get)
        confidence = regime_scores[primary_regime]
        
        # Calculate transition probabilities
        transition_probs = self._calculate_transition_probabilities(
            primary_regime, regime_scores
        )
        
        # Get regime duration
        duration = self._get_regime_duration(primary_regime, current_time)
        
        return RegimeContext(
            regime=primary_regime,
            confidence=confidence,
            regime_duration=duration,
            transition_probability=transition_probs,
            macro_indicators={
                'vix_proxy': vix_level,
                'momentum_signal': momentum_signal,
                'yield_curve_slope': self._get_yield_curve_slope(macro_data)
            }
        )
    
    def _analyze_yield_curve(self, yields: Dict[str, float]) -> Dict[MarketRegime, float]:
        """Analyze yield curve for regime signals"""
        
        scores = {}
        
        # Get key rates
        short_rate = yields.get('3M', 5.0)
        long_rate = yields.get('10Y', 6.0)
        slope = long_rate - short_rate
        
        # Yield curve analysis
        if slope > 2.0:  # Steep curve
            scores[MarketRegime.EXPANSION] = 0.3
            scores[MarketRegime.RECOVERY] = 0.2
        elif slope < -0.5:  # Inverted curve
            scores[MarketRegime.RECESSION] = 0.4
            scores[MarketRegime.SLOWDOWN] = 0.3
        else:  # Flat curve
            scores[MarketRegime.NEUTRAL] = 0.2
        
        # Rate level analysis
        if long_rate > 7.0:  # High rates
            scores[MarketRegime.SLOWDOWN] = scores.get(MarketRegime.SLOWDOWN, 0) + 0.2
        elif long_rate < 4.0:  # Low rates
            scores[MarketRegime.RECOVERY] = scores.get(MarketRegime.RECOVERY, 0) + 0.2
        
        return scores
    
    def _get_vix_proxy(self, current_time: datetime) -> float:
        """Get VIX proxy from market data"""
        
        # Mock VIX calculation based on time (would use real VIX data)
        # Simulate different volatility regimes
        day_of_year = current_time.timetuple().tm_yday
        
        # Create cyclical volatility pattern
        base_vix = 20 + 10 * np.sin(day_of_year / 365 * 2 * np.pi)
        
        # Add some randomness
        noise = np.random.normal(0, 3)
        
        return max(10, min(50, base_vix + noise))
    
    def _analyze_volatility(self, vix_level: float, current_scores: Dict) -> Dict[MarketRegime, float]:
        """Analyze volatility for regime classification"""
        
        scores = {}
        
        if vix_level < self.vix_thresholds['low']:
            scores[MarketRegime.EXPANSION] = 0.4
            scores[MarketRegime.RECOVERY] = 0.2
        elif vix_level < self.vix_thresholds['normal']:
            scores[MarketRegime.EXPANSION] = 0.3
            scores[MarketRegime.NEUTRAL] = 0.2
        elif vix_level < self.vix_thresholds['elevated']:
            scores[MarketRegime.SLOWDOWN] = 0.3
            scores[MarketRegime.NEUTRAL] = 0.2
        else:  # Crisis level
            scores[MarketRegime.CRISIS] = 0.5
            scores[MarketRegime.RECESSION] = 0.3
        
        return scores
    
    def _analyze_market_momentum(self, current_time: datetime) -> float:
        """Analyze broad market momentum"""
        
        # Mock market momentum (would use actual market index data)
        # Simulate momentum based on time patterns
        day_of_year = current_time.timetuple().tm_yday
        
        # Create momentum cycle
        momentum = 0.5 * np.sin(day_of_year / 365 * 2 * np.pi) + np.random.normal(0, 0.2)
        
        return np.clip(momentum, -1, 1)
    
    def _analyze_momentum_patterns(self, momentum: float, current_scores: Dict) -> Dict[MarketRegime, float]:
        """Analyze momentum patterns for regime classification"""
        
        scores = {}
        
        if momentum > 0.3:  # Strong positive momentum
            scores[MarketRegime.EXPANSION] = 0.3
            scores[MarketRegime.RECOVERY] = 0.2
        elif momentum < -0.3:  # Strong negative momentum
            scores[MarketRegime.RECESSION] = 0.4
            scores[MarketRegime.CRISIS] = 0.2
        else:  # Weak momentum
            scores[MarketRegime.NEUTRAL] = 0.2
            scores[MarketRegime.SLOWDOWN] = 0.1
        
        return scores
    
    def _calculate_transition_probabilities(self, current_regime: MarketRegime, 
                                         scores: Dict[MarketRegime, float]) -> Dict[MarketRegime, float]:
        """Calculate regime transition probabilities"""
        
        # Normalize scores to probabilities
        total_score = sum(scores.values())
        if total_score == 0:
            return {regime: 1/len(MarketRegime) for regime in MarketRegime}
        
        return {regime: score/total_score for regime, score in scores.items()}
    
    def _get_regime_duration(self, regime: MarketRegime, current_time: datetime) -> int:
        """Get duration of current regime"""
        
        # Mock duration calculation (would track actual regime changes)
        return 30  # Default 30 days
    
    def _get_yield_curve_slope(self, macro_data: Dict) -> float:
        """Calculate yield curve slope"""
        
        if 'yields' in macro_data:
            yields = macro_data['yields']
            short_rate = yields.get('3M', 5.0)
            long_rate = yields.get('10Y', 6.0)
            return long_rate - short_rate
        
        return 1.5  # Default positive slope

class BaseSpecialist:
    """
    Base class for all signal specialists
    
    Provides common functionality:
    - Temporal protection integration
    - Cross-sectional ranking
    - Regime adaptation
    - Performance tracking
    """
    
    def __init__(self, name: str, guard: TemporalGuard):
        self.name = name
        self.guard = guard
        self.performance_history = []
        
        print(f"🎯 {name} Specialist initialized")
    
    def generate_signal(self, symbol: str, current_time: datetime, 
                       regime_context: RegimeContext) -> SpecialistSignal:
        """Generate signal for a single symbol"""
        raise NotImplementedError("Subclasses must implement generate_signal")
    
    def generate_cross_sectional_signals(self, symbols: List[str], current_time: datetime,
                                       regime_context: RegimeContext) -> List[SpecialistSignal]:
        """Generate cross-sectional signals for universe of symbols"""
        
        # Generate individual signals
        signals = []
        for symbol in symbols:
            try:
                signal = self.generate_signal(symbol, current_time, regime_context)
                if signal is not None:
                    signals.append(signal)
            except Exception as e:
                print(f"⚠️ Error generating {self.name} signal for {symbol}: {e}")
        
        # Add cross-sectional rankings
        if signals:
            signals = self._add_cross_sectional_ranks(signals)
        
        return signals
    
    def _add_cross_sectional_ranks(self, signals: List[SpecialistSignal]) -> List[SpecialistSignal]:
        """Add cross-sectional percentile ranks"""
        
        if not signals:
            return signals
        
        # Extract signal strengths
        strengths = [s.signal_strength for s in signals]
        
        # Calculate percentile ranks
        ranks = pd.Series(strengths).rank(pct=True).values
        
        # Update signals with ranks
        for i, signal in enumerate(signals):
            signal.cross_sectional_rank = ranks[i]
        
        return signals
    
    def get_regime_fit(self, regime_context: RegimeContext) -> float:
        """Calculate how well this specialist fits the current regime"""
        raise NotImplementedError("Subclasses must implement get_regime_fit")

class MomentumSpecialist(BaseSpecialist):
    """
    Momentum Specialist - Optimized for bull markets
    
    Strategy:
    - Multi-horizon momentum (21d/63d/126d) with volatility adjustment
    - Cross-sectional ranking within sectors
    - Regime adaptation: stronger in expansion, weaker in recession
    - Excludes low-liquidity stocks
    """
    
    def __init__(self, guard: TemporalGuard):
        super().__init__("Momentum", guard)
        
        # Momentum parameters
        self.horizons = {
            'short': 21,    # 1 month
            'medium': 63,   # 3 months
            'long': 126     # 6 months
        }
        
        self.weights = {
            'short': 0.5,   # 50% weight on short-term
            'medium': 0.3,  # 30% weight on medium-term
            'long': 0.2     # 20% weight on long-term
        }
    
    def generate_signal(self, symbol: str, current_time: datetime, 
                       regime_context: RegimeContext) -> Optional[SpecialistSignal]:
        """Generate momentum signal with regime adaptation"""
        
        # Get price data through temporal guard
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        
        if price_data.empty or len(price_data) < self.horizons['long']:
            return None
        
        # Calculate momentum components
        price_data = price_data.sort_values('timestamp')
        price_data['returns'] = price_data['Close'].pct_change()
        price_data['volatility'] = price_data['returns'].rolling(21).std()
        
        momentum_components = {}
        
        for horizon_name, horizon_days in self.horizons.items():
            if len(price_data) >= horizon_days:
                # Raw momentum (cumulative return)
                raw_momentum = price_data['returns'].rolling(horizon_days).sum().iloc[-1]
                
                # Volatility adjustment
                recent_vol = price_data['volatility'].iloc[-1]
                if pd.notna(recent_vol) and recent_vol > 0:
                    vol_adjusted = raw_momentum / recent_vol
                else:
                    vol_adjusted = raw_momentum
                
                momentum_components[horizon_name] = {
                    'raw': raw_momentum,
                    'vol_adjusted': vol_adjusted,
                    'weight': self.weights[horizon_name]
                }
        
        # Weighted composite momentum
        weighted_momentum = sum(
            comp['vol_adjusted'] * comp['weight'] 
            for comp in momentum_components.values()
        )
        
        # Regime adaptation
        regime_fit = self.get_regime_fit(regime_context)
        adapted_signal = weighted_momentum * regime_fit
        
        # Normalize to [-2, +2] range
        normalized_signal = np.clip(adapted_signal * 10, -2, 2)
        
        # Calculate confidence based on consistency across horizons
        horizon_signals = [comp['vol_adjusted'] for comp in momentum_components.values()]
        consistency = 1 - np.std(horizon_signals) if len(horizon_signals) > 1 else 0.5
        confidence = np.clip(consistency * regime_fit, 0, 1)
        
        return SpecialistSignal(
            symbol=symbol,
            signal_strength=normalized_signal,
            confidence=confidence,
            regime_fit=regime_fit,
            cross_sectional_rank=0.5,  # Will be updated in cross-sectional ranking
            metadata={
                'components': momentum_components,
                'regime': regime_context.regime.value,
                'volatility': recent_vol
            }
        )
    
    def get_regime_fit(self, regime_context: RegimeContext) -> float:
        """Momentum works best in expansion, poorly in recession"""
        
        regime_fits = {
            MarketRegime.EXPANSION: 1.0,    # Perfect fit
            MarketRegime.RECOVERY: 0.8,     # Good fit
            MarketRegime.NEUTRAL: 0.6,      # Moderate fit
            MarketRegime.SLOWDOWN: 0.4,     # Poor fit
            MarketRegime.RECESSION: 0.2,    # Very poor fit
            MarketRegime.CRISIS: 0.1        # Terrible fit
        }
        
        base_fit = regime_fits.get(regime_context.regime, 0.5)
        
        # Adjust for regime confidence
        return base_fit * regime_context.confidence + 0.3 * (1 - regime_context.confidence)

class ValueSpecialist(BaseSpecialist):
    """
    Value Specialist - Optimized for bear markets
    
    Strategy:
    - Multi-factor value scoring (P/E, P/B, FCF yield, ROIC)
    - Excludes highly leveraged and negative FCF stocks
    - Regime adaptation: stronger in recession, weaker in expansion
    - Uses trailing 12-month fundamentals
    """
    
    def __init__(self, guard: TemporalGuard):
        super().__init__("Value", guard)
        
        # Value factor weights
        self.factor_weights = {
            'earnings_yield': 0.4,  # 40% weight (inverse P/E)
            'book_yield': 0.3,      # 30% weight (inverse P/B)
            'quality': 0.2,         # 20% weight (ROE, debt levels)
            'momentum': 0.1         # 10% weight (avoid falling knives)
        }
    
    def generate_signal(self, symbol: str, current_time: datetime, 
                       regime_context: RegimeContext) -> Optional[SpecialistSignal]:
        """Generate value signal with fundamental analysis"""
        
        # Get fundamental data through temporal guard
        fundamental_data = self.guard.get_data(symbol, current_time, 'fundamentals')
        
        if fundamental_data.empty:
            # Fallback to price-based value proxy
            return self._generate_price_based_value(symbol, current_time, regime_context)
        
        # Get latest fundamental data
        fundamental_data = fundamental_data.sort_values('timestamp')
        latest = fundamental_data.iloc[-1]
        
        value_components = {}
        
        # Earnings yield (inverse P/E)
        pe_ratio = latest.get('PE', 15.0)
        if pe_ratio > 0:
            earnings_yield = 1 / pe_ratio
            # Normalize: higher earnings yield = cheaper
            value_components['earnings_yield'] = (earnings_yield - 0.05) * 20
        else:
            value_components['earnings_yield'] = 0.0
        
        # Book yield (inverse P/B)
        pb_ratio = latest.get('PB', 2.0)
        if pb_ratio > 0:
            book_yield = 1 / pb_ratio
            # Normalize: higher book yield = cheaper
            value_components['book_yield'] = (book_yield - 0.5) * 2
        else:
            value_components['book_yield'] = 0.0
        
        # Quality factors
        roe = latest.get('ROE', 15.0)
        debt_equity = latest.get('DebtToEquity', 0.5)
        
        # Quality score: high ROE, low debt
        quality_score = (roe - 15) / 15 - (debt_equity - 0.5) / 0.5
        value_components['quality'] = quality_score
        
        # Momentum component (avoid falling knives)
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        if not price_data.empty and len(price_data) >= 63:
            price_data = price_data.sort_values('timestamp')
            returns = price_data['Close'].pct_change()
            momentum_3m = returns.rolling(63).sum().iloc[-1]
            value_components['momentum'] = momentum_3m * 5  # Scale momentum
        else:
            value_components['momentum'] = 0.0
        
        # Weighted composite value score
        weighted_value = sum(
            value_components[component] * self.factor_weights[component]
            for component in self.factor_weights.keys()
        )
        
        # Regime adaptation
        regime_fit = self.get_regime_fit(regime_context)
        adapted_signal = weighted_value * regime_fit
        
        # Normalize to [-2, +2] range
        normalized_signal = np.clip(adapted_signal, -2, 2)
        
        # Calculate confidence based on factor consistency
        factor_values = list(value_components.values())
        consistency = 1 - np.std(factor_values) / (np.mean(np.abs(factor_values)) + 1e-6)
        confidence = np.clip(consistency * regime_fit, 0, 1)
        
        return SpecialistSignal(
            symbol=symbol,
            signal_strength=normalized_signal,
            confidence=confidence,
            regime_fit=regime_fit,
            cross_sectional_rank=0.5,
            metadata={
                'components': value_components,
                'pe_ratio': pe_ratio,
                'pb_ratio': pb_ratio,
                'roe': roe,
                'debt_equity': debt_equity
            }
        )
    
    def _generate_price_based_value(self, symbol: str, current_time: datetime,
                                  regime_context: RegimeContext) -> Optional[SpecialistSignal]:
        """Fallback value signal using price mean reversion"""
        
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        
        if price_data.empty or len(price_data) < 252:
            return None
        
        price_data = price_data.sort_values('timestamp')
        current_price = price_data['Close'].iloc[-1]
        
        # Mean reversion signal
        avg_price_1y = price_data['Close'].tail(252).mean()
        value_signal = (avg_price_1y - current_price) / current_price
        
        # Regime adaptation
        regime_fit = self.get_regime_fit(regime_context)
        adapted_signal = value_signal * regime_fit
        
        normalized_signal = np.clip(adapted_signal * 5, -2, 2)
        
        return SpecialistSignal(
            symbol=symbol,
            signal_strength=normalized_signal,
            confidence=0.5 * regime_fit,
            regime_fit=regime_fit,
            cross_sectional_rank=0.5,
            metadata={
                'method': 'price_based_fallback',
                'current_price': current_price,
                'avg_price_1y': avg_price_1y
            }
        )
    
    def get_regime_fit(self, regime_context: RegimeContext) -> float:
        """Value works best in recession, poorly in expansion"""
        
        regime_fits = {
            MarketRegime.RECESSION: 1.0,    # Perfect fit
            MarketRegime.CRISIS: 0.9,       # Very good fit
            MarketRegime.SLOWDOWN: 0.7,     # Good fit
            MarketRegime.NEUTRAL: 0.5,      # Moderate fit
            MarketRegime.RECOVERY: 0.3,     # Poor fit
            MarketRegime.EXPANSION: 0.2     # Very poor fit
        }
        
        base_fit = regime_fits.get(regime_context.regime, 0.5)
        
        # Adjust for regime confidence
        return base_fit * regime_context.confidence + 0.4 * (1 - regime_context.confidence)

class QualitySpecialist(BaseSpecialist):
    """
    Quality Specialist - Defensive positioning for uncertain markets
    
    Strategy:
    - Focus on high ROE, low debt, stable earnings
    - 3-year averages to avoid cyclical distortions
    - Regime adaptation: stronger in crisis/slowdown
    - Emphasizes balance sheet strength
    """
    
    def __init__(self, guard: TemporalGuard):
        super().__init__("Quality", guard)
        
        # Quality factor weights
        self.factor_weights = {
            'profitability': 0.4,   # ROE, margins
            'stability': 0.3,       # Earnings stability
            'balance_sheet': 0.2,   # Debt levels, coverage
            'growth': 0.1          # Sustainable growth
        }
    
    def generate_signal(self, symbol: str, current_time: datetime, 
                       regime_context: RegimeContext) -> Optional[SpecialistSignal]:
        """Generate quality signal focusing on defensive characteristics"""
        
        # Get fundamental data
        fundamental_data = self.guard.get_data(symbol, current_time, 'fundamentals')
        
        if fundamental_data.empty:
            return self._generate_price_based_quality(symbol, current_time, regime_context)
        
        fundamental_data = fundamental_data.sort_values('timestamp')
        
        # Use multiple periods for stability (3-year average)
        if len(fundamental_data) >= 12:  # 3 years of quarterly data
            recent_data = fundamental_data.tail(12)
        else:
            recent_data = fundamental_data
        
        quality_components = {}
        
        # Profitability metrics
        try:
            roe_values = recent_data['ROE'].dropna()
        except KeyError:
            # ROE column doesn't exist, use fallback
            roe_values = pd.Series([])
        
        if len(roe_values) > 0:
            avg_roe = roe_values.mean()
            quality_components['profitability'] = (avg_roe - 15) / 15
        else:
            # Fallback: use a neutral profitability score
            quality_components['profitability'] = 0.0
        
        # Earnings stability (lower volatility = higher quality)
        if len(roe_values) > 1:
            roe_stability = 1 / (1 + roe_values.std())
            quality_components['stability'] = roe_stability - 0.5
        else:
            quality_components['stability'] = 0.0
        
        # Balance sheet strength
        try:
            debt_equity_values = recent_data['DebtToEquity'].dropna()
        except KeyError:
            # DebtToEquity column doesn't exist, use fallback
            debt_equity_values = pd.Series([])
        
        if len(debt_equity_values) > 0:
            avg_debt_equity = debt_equity_values.mean()
            # Lower debt = higher quality
            quality_components['balance_sheet'] = (0.5 - avg_debt_equity) / 0.5
        else:
            # Fallback: assume moderate debt levels
            quality_components['balance_sheet'] = 0.0
        
        # Growth quality (sustainable growth)
        if len(roe_values) > 4:  # Need some history
            growth_trend = np.polyfit(range(len(roe_values)), roe_values, 1)[0]
            quality_components['growth'] = np.clip(growth_trend / 5, -1, 1)
        else:
            quality_components['growth'] = 0.0
        
        # Weighted composite quality score
        weighted_quality = sum(
            quality_components[component] * self.factor_weights[component]
            for component in self.factor_weights.keys()
        )
        
        # Regime adaptation
        regime_fit = self.get_regime_fit(regime_context)
        adapted_signal = weighted_quality * regime_fit
        
        # Normalize to [-2, +2] range
        normalized_signal = np.clip(adapted_signal, -2, 2)
        
        # Calculate confidence
        factor_values = list(quality_components.values())
        consistency = 1 - np.std(factor_values) / (np.mean(np.abs(factor_values)) + 1e-6)
        confidence = np.clip(consistency * regime_fit, 0, 1)
        
        return SpecialistSignal(
            symbol=symbol,
            signal_strength=normalized_signal,
            confidence=confidence,
            regime_fit=regime_fit,
            cross_sectional_rank=0.5,
            metadata={
                'components': quality_components,
                'data_periods': len(recent_data),
                'avg_roe': roe_values.mean() if len(roe_values) > 0 else None
            }
        )
    
    def _generate_price_based_quality(self, symbol: str, current_time: datetime,
                                    regime_context: RegimeContext) -> Optional[SpecialistSignal]:
        """Fallback quality signal using price volatility"""
        
        price_data = self.guard.get_data(symbol, current_time, 'prices')
        
        if price_data.empty or len(price_data) < 252:
            return None
        
        price_data = price_data.sort_values('timestamp')
        price_data['returns'] = price_data['Close'].pct_change()
        
        # Quality = low volatility (defensive characteristic)
        volatility_1y = price_data['returns'].tail(252).std() * np.sqrt(252)
        
        # Lower volatility = higher quality
        quality_signal = (0.20 - volatility_1y) / 0.20
        
        # Regime adaptation
        regime_fit = self.get_regime_fit(regime_context)
        adapted_signal = quality_signal * regime_fit
        
        normalized_signal = np.clip(adapted_signal * 2, -2, 2)
        
        return SpecialistSignal(
            symbol=symbol,
            signal_strength=normalized_signal,
            confidence=0.6 * regime_fit,
            regime_fit=regime_fit,
            cross_sectional_rank=0.5,
            metadata={
                'method': 'volatility_proxy',
                'volatility_1y': volatility_1y
            }
        )
    
    def get_regime_fit(self, regime_context: RegimeContext) -> float:
        """Quality works best in crisis/slowdown, moderately in other regimes"""
        
        regime_fits = {
            MarketRegime.CRISIS: 1.0,       # Perfect fit
            MarketRegime.SLOWDOWN: 0.8,     # Very good fit
            MarketRegime.RECESSION: 0.7,    # Good fit
            MarketRegime.NEUTRAL: 0.6,      # Moderate fit
            MarketRegime.RECOVERY: 0.5,     # Moderate fit
            MarketRegime.EXPANSION: 0.4     # Lower fit
        }
        
        base_fit = regime_fits.get(regime_context.regime, 0.6)
        
        # Quality is always somewhat useful, so higher baseline
        return base_fit * regime_context.confidence + 0.5 * (1 - regime_context.confidence)

class MacroSpecialist(BaseSpecialist):
    """
    Macro Specialist - Regime-based sector and factor positioning
    
    Strategy:
    - Sector rotation based on regime (Tech in expansion, Utilities in recession)
    - Factor tilts (Growth vs Value, Large vs Small)
    - Interest rate sensitivity analysis
    - Currency and commodity exposure
    """
    
    def __init__(self, guard: TemporalGuard):
        super().__init__("Macro", guard)
        
        # Sector preferences by regime
        self.sector_preferences = {
            MarketRegime.EXPANSION: {
                'Technology': 1.0, 'Consumer Discretionary': 0.8, 'Financials': 0.6
            },
            MarketRegime.RECESSION: {
                'Utilities': 1.0, 'Consumer Staples': 0.8, 'Healthcare': 0.6
            },
            MarketRegime.RECOVERY: {
                'Industrials': 1.0, 'Materials': 0.8, 'Energy': 0.6
            },
            MarketRegime.SLOWDOWN: {
                'Healthcare': 1.0, 'Utilities': 0.8, 'Consumer Staples': 0.6
            },
            MarketRegime.CRISIS: {
                'Utilities': 1.0, 'Consumer Staples': 0.9, 'Healthcare': 0.8
            }
        }
    
    def generate_signal(self, symbol: str, current_time: datetime, 
                       regime_context: RegimeContext) -> Optional[SpecialistSignal]:
        """Generate macro signal based on regime positioning"""
        
        # Get sector classification (mock for now)
        sector = self._get_sector(symbol)
        
        # Get macro indicators
        macro_data = self.guard.get_macro_data(current_time)
        
        macro_components = {}
        
        # Sector positioning signal
        sector_prefs = self.sector_preferences.get(regime_context.regime, {})
        sector_signal = sector_prefs.get(sector, 0.5)
        macro_components['sector'] = (sector_signal - 0.5) * 2
        
        # Interest rate sensitivity
        if 'yields' in macro_data:
            rate_signal = self._analyze_rate_sensitivity(symbol, macro_data['yields'])
            macro_components['rates'] = rate_signal
        else:
            macro_components['rates'] = 0.0
        
        # Liquidity cycle signal
        liquidity_signal = self._analyze_liquidity_cycle(regime_context)
        macro_components['liquidity'] = liquidity_signal
        
        # Currency exposure (mock)
        currency_signal = self._analyze_currency_exposure(symbol, regime_context)
        macro_components['currency'] = currency_signal
        
        # Weighted composite macro score
        weights = {
            'sector': 0.4,      # 40% weight
            'rates': 0.3,       # 30% weight
            'liquidity': 0.2,   # 20% weight
            'currency': 0.1     # 10% weight
        }
        
        weighted_macro = sum(
            macro_components[component] * weights[component]
            for component in weights.keys()
        )
        
        # Regime adaptation
        regime_fit = self.get_regime_fit(regime_context)
        adapted_signal = weighted_macro * regime_fit
        
        # Normalize to [-2, +2] range
        normalized_signal = np.clip(adapted_signal, -2, 2)
        
        # Calculate confidence
        confidence = regime_context.confidence * 0.8  # Macro signals depend on regime confidence
        
        return SpecialistSignal(
            symbol=symbol,
            signal_strength=normalized_signal,
            confidence=confidence,
            regime_fit=regime_fit,
            cross_sectional_rank=0.5,
            metadata={
                'components': macro_components,
                'sector': sector,
                'regime': regime_context.regime.value
            }
        )
    
    def _get_sector(self, symbol: str) -> str:
        """Get sector classification for symbol (mock implementation)"""
        
        # Mock sector classification based on symbol
        sector_map = {
            'RELIANCE.NS': 'Energy',
            'TCS.NS': 'Technology',
            'INFY.NS': 'Technology',
            'HDFCBANK.NS': 'Financials',
            'ICICIBANK.NS': 'Financials'
        }
        
        return sector_map.get(symbol, 'Industrials')  # Default sector
    
    def _analyze_rate_sensitivity(self, symbol: str, yields: Dict[str, float]) -> float:
        """Analyze interest rate sensitivity"""
        
        # Mock rate sensitivity analysis
        sector = self._get_sector(symbol)
        
        # Rate sensitive sectors
        rate_sensitivity = {
            'Financials': 0.5,      # Positive rate sensitivity
            'Utilities': -0.5,      # Negative rate sensitivity
            'Technology': -0.3,     # Somewhat negative
            'Energy': 0.2,          # Somewhat positive
            'Industrials': 0.0      # Neutral
        }
        
        sensitivity = rate_sensitivity.get(sector, 0.0)
        
        # Current rate level vs neutral (6%)
        current_rate = yields.get('10Y', 6.0)
        rate_deviation = (current_rate - 6.0) / 2.0  # Normalize
        
        return sensitivity * rate_deviation
    
    def _analyze_liquidity_cycle(self, regime_context: RegimeContext) -> float:
        """Analyze liquidity cycle positioning"""
        
        # Liquidity preferences by regime
        liquidity_signals = {
            MarketRegime.EXPANSION: 0.3,    # Moderate liquidity preference
            MarketRegime.RECOVERY: 0.5,     # High liquidity preference
            MarketRegime.SLOWDOWN: -0.2,    # Slight liquidity aversion
            MarketRegime.RECESSION: -0.5,   # Strong liquidity aversion
            MarketRegime.CRISIS: -0.8,      # Very strong liquidity aversion
            MarketRegime.NEUTRAL: 0.0       # Neutral
        }
        
        return liquidity_signals.get(regime_context.regime, 0.0)
    
    def _analyze_currency_exposure(self, symbol: str, regime_context: RegimeContext) -> float:
        """Analyze currency exposure impact"""
        
        # Mock currency analysis (would use actual currency data)
        # Assume domestic companies have neutral exposure
        return 0.0
    
    def get_regime_fit(self, regime_context: RegimeContext) -> float:
        """Macro specialist works well across all regimes"""
        
        # Macro signals are always relevant, but effectiveness varies
        regime_fits = {
            MarketRegime.EXPANSION: 0.8,
            MarketRegime.RECOVERY: 0.9,     # Best fit - regime transitions
            MarketRegime.SLOWDOWN: 0.8,
            MarketRegime.RECESSION: 0.7,
            MarketRegime.CRISIS: 0.6,       # Lower fit - fundamentals matter more
            MarketRegime.NEUTRAL: 0.5       # Moderate fit
        }
        
        base_fit = regime_fits.get(regime_context.regime, 0.7)
        
        # Macro signals depend heavily on regime confidence
        return base_fit * regime_context.confidence + 0.3 * (1 - regime_context.confidence)

class RegimeAwareSpecialists:
    """
    Main orchestrator for regime-aware signal specialists
    
    Coordinates all specialists and provides unified interface:
    - Regime detection and context
    - Specialist signal generation
    - Cross-sectional ranking
    - Performance tracking
    """
    
    def __init__(self):
        self.guard = TemporalGuard()
        self.regime_detector = RegimeDetector(self.guard)
        
        # Initialize specialists
        self.specialists = {
            'momentum': MomentumSpecialist(self.guard),
            'value': ValueSpecialist(self.guard),
            'quality': QualitySpecialist(self.guard),
            'macro': MacroSpecialist(self.guard)
        }
        
        print("🎯 Regime-Aware Specialists initialized - Layer 4 active")
    
    def generate_regime_signals(self, symbols: List[str], current_time: datetime) -> Dict[str, Any]:
        """Generate regime-aware signals for all specialists"""
        
        # Detect current regime
        regime_context = self.regime_detector.detect_regime(current_time)
        
        print(f"📊 Current regime: {regime_context.regime.value} "
              f"(confidence: {regime_context.confidence:.2f})")
        
        # Generate signals from all specialists
        all_signals = {}
        
        for specialist_name, specialist in self.specialists.items():
            try:
                signals = specialist.generate_cross_sectional_signals(
                    symbols, current_time, regime_context
                )
                all_signals[specialist_name] = signals
                
                print(f"   {specialist_name.capitalize()}: {len(signals)} signals generated")
                
            except Exception as e:
                print(f"❌ Error in {specialist_name} specialist: {e}")
                all_signals[specialist_name] = []
        
        return {
            'regime_context': regime_context,
            'signals': all_signals,
            'timestamp': current_time.isoformat(),
            'universe_size': len(symbols)
        }
    
    def get_specialist_performance(self, specialist_name: str) -> Dict[str, Any]:
        """Get performance metrics for a specialist"""
        
        if specialist_name not in self.specialists:
            return {}
        
        specialist = self.specialists[specialist_name]
        
        return {
            'name': specialist.name,
            'performance_history': specialist.performance_history,
            'total_signals': len(specialist.performance_history)
        }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate regime-aware specialists"""
    
    print("🎯 REGIME-AWARE SIGNAL SPECIALISTS - LAYER 4")
    print("=" * 70)
    
    # Initialize specialists
    specialists = RegimeAwareSpecialists()
    
    # Test symbols
    test_symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS']
    test_time = datetime(2024, 1, 15)
    
    print(f"\n📊 Generating regime-aware signals for {len(test_symbols)} symbols")
    print(f"📅 Test time: {test_time}")
    
    # Generate signals
    results = specialists.generate_regime_signals(test_symbols, test_time)
    
    # Display results
    regime = results['regime_context']
    print(f"\n🎯 Regime Analysis:")
    print(f"   Current regime: {regime.regime.value}")
    print(f"   Confidence: {regime.confidence:.2f}")
    print(f"   Duration: {regime.regime_duration} days")
    
    print(f"\n📈 Signal Summary:")
    for specialist_name, signals in results['signals'].items():
        if signals:
            avg_signal = np.mean([s.signal_strength for s in signals])
            avg_confidence = np.mean([s.confidence for s in signals])
            avg_regime_fit = np.mean([s.regime_fit for s in signals])
            
            print(f"   {specialist_name.capitalize()}:")
            print(f"      Signals: {len(signals)}")
            print(f"      Avg strength: {avg_signal:+.3f}")
            print(f"      Avg confidence: {avg_confidence:.3f}")
            print(f"      Avg regime fit: {avg_regime_fit:.3f}")
        else:
            print(f"   {specialist_name.capitalize()}: No signals generated")
    
    print(f"\n✅ Layer 4 (Regime-Aware Specialists) demonstration complete")
    print("💡 All specialists now adapt to market regimes with temporal protection")

if __name__ == "__main__":
    main()