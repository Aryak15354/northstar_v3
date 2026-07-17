#!/usr/bin/env python3
"""
🎯 CONFIDENCE ENGINE - HEDGE FUND GRADE UNCERTAINTY QUANTIFICATION
Institutional-Grade Confidence Weighting for Northstar V3

This prevents fake signals from garbage data by calculating confidence for every signal:
confidence = data_coverage × data_freshness × volatility_stability

Instead of:
    Mispricing = -1.8

You get:
    Effective Mispricing = -1.8 × 0.21 = -0.38

This is how real hedge funds avoid getting fooled by noisy data.

Usage:
    try:
    from src.intelligence.confidence_engine import ConfidenceEngine
except ImportError:
    from ConfidenceEngine import ConfidenceEngine
    
    engine = ConfidenceEngine()
    confidence = engine.calculate_signal_confidence(
        data_coverage=0.6,
        data_freshness=0.7, 
        volatility_stability=0.5
    )
    
    effective_signal = raw_signal * confidence
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import logging
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

# =========================== CONFIDENCE CALCULATION FRAMEWORK ===========================

class ConfidenceEngine:
    """
    Hedge Fund Grade Confidence Engine
    
    Calculates confidence for every signal to prevent fake signals from garbage data.
    
    Three pillars of confidence:
    1. Data Coverage - How complete is the data?
    2. Data Freshness - How recent is the data?
    3. Volatility Stability - How stable/reliable is the signal?
    """
    
    def __init__(self):
        self.name = "Confidence Engine"
        
        # Confidence thresholds
        self.coverage_thresholds = {
            'excellent': 0.9,
            'good': 0.7,
            'acceptable': 0.5,
            'poor': 0.3
        }
        
        self.freshness_thresholds = {
            'real_time': 1.0,      # Same day
            'fresh': 0.9,          # 1-3 days
            'recent': 0.7,         # 1 week
            'stale': 0.5,          # 1 month
            'old': 0.3             # 3+ months
        }
        
        self.stability_thresholds = {
            'very_stable': 0.9,    # Low volatility, consistent signal
            'stable': 0.7,         # Moderate volatility
            'unstable': 0.5,       # High volatility
            'very_unstable': 0.3   # Extreme volatility
        }
    
    def calculate_data_coverage(self, required_fields, available_fields, field_weights=None):
        """
        Calculate data coverage confidence
        
        Args:
            required_fields: List of required data fields
            available_fields: Dict of available fields with their values
            field_weights: Optional dict of field importance weights
        
        Returns:
            float: Coverage confidence (0-1)
        """
        
        if not required_fields:
            return 1.0
        
        if field_weights is None:
            field_weights = {field: 1.0 for field in required_fields}
        
        total_weight = sum(field_weights.values())
        covered_weight = 0.0
        
        for field in required_fields:
            if field in available_fields:
                value = available_fields[field]
                # Check if value is not null/nan/empty
                if pd.notna(value) and value != '' and value != 0:
                    covered_weight += field_weights.get(field, 1.0)
        
        coverage_ratio = covered_weight / total_weight if total_weight > 0 else 0.0
        
        # Apply coverage quality curve
        if coverage_ratio >= self.coverage_thresholds['excellent']:
            return 1.0
        elif coverage_ratio >= self.coverage_thresholds['good']:
            return 0.8 + 0.2 * (coverage_ratio - self.coverage_thresholds['good']) / (self.coverage_thresholds['excellent'] - self.coverage_thresholds['good'])
        elif coverage_ratio >= self.coverage_thresholds['acceptable']:
            return 0.6 + 0.2 * (coverage_ratio - self.coverage_thresholds['acceptable']) / (self.coverage_thresholds['good'] - self.coverage_thresholds['acceptable'])
        elif coverage_ratio >= self.coverage_thresholds['poor']:
            return 0.3 + 0.3 * (coverage_ratio - self.coverage_thresholds['poor']) / (self.coverage_thresholds['acceptable'] - self.coverage_thresholds['poor'])
        else:
            return 0.1 + 0.2 * (coverage_ratio / self.coverage_thresholds['poor'])
    
    def calculate_data_freshness(self, data_timestamp, reference_timestamp=None):
        """
        Calculate data freshness confidence
        
        Args:
            data_timestamp: When the data was last updated
            reference_timestamp: Reference time (default: now)
        
        Returns:
            float: Freshness confidence (0-1)
        """
        
        if reference_timestamp is None:
            reference_timestamp = datetime.now()
        
        if pd.isna(data_timestamp):
            return 0.2  # Very low confidence for unknown age
        
        # Convert to datetime if needed
        if isinstance(data_timestamp, str):
            try:
                data_timestamp = pd.to_datetime(data_timestamp)
            except:
                return 0.2
        
        # Calculate age in hours
        age_hours = (reference_timestamp - data_timestamp).total_seconds() / 3600
        
        # Freshness decay curve
        if age_hours <= 24:  # Same day
            return 1.0
        elif age_hours <= 72:  # 1-3 days
            return 0.9 - 0.1 * (age_hours - 24) / 48
        elif age_hours <= 168:  # 1 week
            return 0.8 - 0.1 * (age_hours - 72) / 96
        elif age_hours <= 720:  # 1 month
            return 0.5 - 0.2 * (age_hours - 168) / 552
        elif age_hours <= 2160:  # 3 months
            return 0.3 - 0.2 * (age_hours - 720) / 1440
        else:  # Very old
            return 0.1
    
    def calculate_volatility_stability(self, signal_history, lookback_periods=20):
        """
        Calculate signal stability based on historical volatility
        
        Args:
            signal_history: List or Series of historical signal values
            lookback_periods: Number of periods to analyze
        
        Returns:
            float: Stability confidence (0-1)
        """
        
        if not signal_history or len(signal_history) < 3:
            return 0.3  # Low confidence for insufficient history
        
        # Convert to numpy array
        if isinstance(signal_history, (list, pd.Series)):
            signal_array = np.array(signal_history)
        else:
            signal_array = signal_history
        
        # Take last N periods
        recent_signals = signal_array[-lookback_periods:] if len(signal_array) >= lookback_periods else signal_array
        
        if len(recent_signals) < 3:
            return 0.3
        
        # Calculate signal statistics
        signal_mean = np.mean(recent_signals)
        signal_std = np.std(recent_signals)
        signal_range = np.max(recent_signals) - np.min(recent_signals)
        
        # Coefficient of variation (normalized volatility)
        if abs(signal_mean) > 1e-6:
            cv = signal_std / abs(signal_mean)
        else:
            cv = signal_std  # If mean is near zero, use raw std
        
        # Stability scoring
        if cv <= 0.1:  # Very stable
            return 0.95
        elif cv <= 0.2:  # Stable
            return 0.8 - 0.15 * (cv - 0.1) / 0.1
        elif cv <= 0.5:  # Moderate volatility
            return 0.6 - 0.2 * (cv - 0.2) / 0.3
        elif cv <= 1.0:  # High volatility
            return 0.4 - 0.2 * (cv - 0.5) / 0.5
        else:  # Very unstable
            return 0.2
    
    def calculate_signal_confidence(self, data_coverage=None, data_freshness=None, 
                                  volatility_stability=None, weights=None):
        """
        Calculate overall signal confidence
        
        Formula: confidence = data_coverage × data_freshness × volatility_stability
        
        Args:
            data_coverage: Coverage confidence (0-1)
            data_freshness: Freshness confidence (0-1)
            volatility_stability: Stability confidence (0-1)
            weights: Optional weights for each component
        
        Returns:
            dict: Detailed confidence breakdown
        """
        
        if weights is None:
            weights = {'coverage': 0.4, 'freshness': 0.3, 'stability': 0.3}
        
        # Default values if not provided
        coverage_conf = data_coverage if data_coverage is not None else 0.5
        freshness_conf = data_freshness if data_freshness is not None else 0.5
        stability_conf = volatility_stability if volatility_stability is not None else 0.5
        
        # Weighted combination
        overall_confidence = (
            weights['coverage'] * coverage_conf +
            weights['freshness'] * freshness_conf +
            weights['stability'] * stability_conf
        )
        
        # Alternative: Multiplicative (more conservative)
        multiplicative_confidence = coverage_conf * freshness_conf * stability_conf
        
        # Use the more conservative approach
        final_confidence = min(overall_confidence, multiplicative_confidence * 1.2)
        final_confidence = max(0.05, min(1.0, final_confidence))  # Clamp to [0.05, 1.0]
        
        # Confidence grade
        if final_confidence >= 0.8:
            grade = 'A'
        elif final_confidence >= 0.6:
            grade = 'B'
        elif final_confidence >= 0.4:
            grade = 'C'
        elif final_confidence >= 0.2:
            grade = 'D'
        else:
            grade = 'F'
        
        return {
            'overall_confidence': final_confidence,
            'grade': grade,
            'components': {
                'data_coverage': coverage_conf,
                'data_freshness': freshness_conf,
                'volatility_stability': stability_conf
            },
            'weighted_score': overall_confidence,
            'multiplicative_score': multiplicative_confidence,
            'weights': weights
        }
    
    def apply_confidence_to_signal(self, raw_signal, confidence_result):
        """
        Apply confidence weighting to raw signal
        
        This is the key function that prevents fake signals from garbage data.
        
        Args:
            raw_signal: Raw signal value
            confidence_result: Result from calculate_signal_confidence()
        
        Returns:
            dict: Confidence-adjusted signal
        """
        
        confidence = confidence_result['overall_confidence']
        
        # Effective signal = raw_signal × confidence
        effective_signal = raw_signal * confidence
        
        # Signal reliability assessment
        if confidence >= 0.8:
            reliability = 'High'
        elif confidence >= 0.6:
            reliability = 'Medium'
        elif confidence >= 0.4:
            reliability = 'Low'
        else:
            reliability = 'Very Low'
        
        return {
            'raw_signal': raw_signal,
            'effective_signal': effective_signal,
            'confidence': confidence,
            'confidence_grade': confidence_result['grade'],
            'reliability': reliability,
            'confidence_adjustment': confidence,
            'signal_strength': abs(effective_signal),
            'actionable': confidence >= 0.4  # Only act on signals with 40%+ confidence
        }
    
    def calculate_sentiment_confidence(self, sentiment_state):
        """
        Calculate confidence modifier based on sentiment clarity.
        
        High confidence when: sentiment regime is clear (not at a boundary),
        sentiment is fresh, and sentiment aligns with price action.
        
        Low confidence when: sentiment is stale, or sentiment strongly
        contradicts what price action is saying (divergence).
        
        Args:
            sentiment_state: SentimentState object
            
        Returns:
            float: Confidence score between 0.1 and 1.0
        """
        try:
            from src.intelligence.sentiment_integration import compute_sentiment_confidence
            return compute_sentiment_confidence(sentiment_state)
        except Exception as e:
            logger.warning(f"Could not compute sentiment confidence: {e}")
            return 0.5  # Neutral fallback

# =========================== SPECIALIZED CONFIDENCE CALCULATORS ===========================

class ValuationConfidenceCalculator:
    """
    Specialized confidence calculator for valuation signals
    """
    
    def __init__(self):
        self.engine = ConfidenceEngine()
        
        # Valuation-specific field requirements
        self.fundamental_fields = ['pe_ratio', 'pb_ratio', 'roe', 'debt_equity', 'revenue_growth']
        self.macro_fields = ['macro_score', 'liquidity', 'inflation', 'growth']
        self.relative_fields = ['sector_pe', 'sector_pb', 'peer_comparison']
        self.market_fields = ['price_momentum', 'volume', 'volatility']
        
        # Field importance weights
        self.field_weights = {
            'pe_ratio': 1.0,
            'pb_ratio': 0.8,
            'roe': 0.9,
            'debt_equity': 0.7,
            'revenue_growth': 0.6,
            'macro_score': 1.0,
            'liquidity': 0.8,
            'inflation': 0.7,
            'growth': 0.8,
            'price_momentum': 0.9,
            'volume': 0.6,
            'volatility': 0.7
        }
    
    def calculate_fundamental_confidence(self, fundamental_data, data_timestamp=None):
        """Calculate confidence for fundamental valuation"""
        
        # Data coverage
        coverage = self.engine.calculate_data_coverage(
            self.fundamental_fields, 
            fundamental_data, 
            self.field_weights
        )
        
        # Data freshness
        freshness = self.engine.calculate_data_freshness(data_timestamp)
        
        # Stability (would need historical fundamental data)
        stability = 0.7  # Default assumption for fundamental data
        
        return self.engine.calculate_signal_confidence(coverage, freshness, stability)
    
    def calculate_macro_confidence(self, macro_data, macro_history=None):
        """Calculate confidence for macro-adjusted valuation"""
        
        # Data coverage
        coverage = self.engine.calculate_data_coverage(
            self.macro_fields,
            macro_data,
            self.field_weights
        )
        
        # Data freshness (macro data should be recent)
        freshness = self.engine.calculate_data_freshness(
            macro_data.get('timestamp', datetime.now())
        )
        
        # Stability from macro score history
        if macro_history:
            stability = self.engine.calculate_volatility_stability(macro_history)
        else:
            stability = 0.6  # Default
        
        return self.engine.calculate_signal_confidence(coverage, freshness, stability)
    
    def calculate_relative_confidence(self, relative_data, sector_data_quality=None):
        """Calculate confidence for relative valuation"""
        
        # Data coverage
        coverage = self.engine.calculate_data_coverage(
            self.relative_fields,
            relative_data,
            self.field_weights
        )
        
        # Freshness
        freshness = self.engine.calculate_data_freshness(
            relative_data.get('timestamp', datetime.now())
        )
        
        # Stability (sector comparisons are generally stable)
        stability = sector_data_quality if sector_data_quality else 0.8
        
        return self.engine.calculate_signal_confidence(coverage, freshness, stability)
    
    def calculate_market_implied_confidence(self, market_data, price_history=None):
        """Calculate confidence for market-implied valuation"""
        
        # Data coverage
        coverage = self.engine.calculate_data_coverage(
            self.market_fields,
            market_data,
            self.field_weights
        )
        
        # Freshness (market data should be very fresh)
        freshness = self.engine.calculate_data_freshness(
            market_data.get('timestamp', datetime.now())
        )
        
        # Stability from price history
        if price_history:
            # Calculate price volatility
            returns = np.diff(price_history) / price_history[:-1]
            stability = self.engine.calculate_volatility_stability(returns)
        else:
            stability = 0.5  # Default
        
        return self.engine.calculate_signal_confidence(coverage, freshness, stability)

class MacroConfidenceCalculator:
    """
    Specialized confidence calculator for macro signals
    """
    
    def __init__(self):
        self.engine = ConfidenceEngine()
        
        # RBI data field requirements
        self.rbi_fields = ['growth_rate', 'inflation_rate', 'repo_rate', 'liquidity_ratio', 'credit_growth']
        self.market_fields = ['nifty_level', 'sector_breadth', 'volatility', 'volume']
        
    def calculate_rbi_data_confidence(self, rbi_data, data_timestamp=None):
        """Calculate confidence for RBI macro data"""
        
        # Coverage
        coverage = self.engine.calculate_data_coverage(self.rbi_fields, rbi_data)
        
        # Freshness (RBI data is monthly, so different freshness curve)
        if data_timestamp:
            age_days = (datetime.now() - pd.to_datetime(data_timestamp)).days
            if age_days <= 45:  # Within 1.5 months
                freshness = 1.0
            elif age_days <= 90:  # Within 3 months
                freshness = 0.8
            elif age_days <= 180:  # Within 6 months
                freshness = 0.6
            else:
                freshness = 0.3
        else:
            freshness = 0.5
        
        # Stability (RBI data is generally stable)
        stability = 0.8
        
        return self.engine.calculate_signal_confidence(coverage, freshness, stability)
    
    def calculate_market_health_confidence(self, market_data, market_history=None):
        """Calculate confidence for market health signals"""
        
        # Coverage
        coverage = self.engine.calculate_data_coverage(self.market_fields, market_data)
        
        # Freshness (market data should be real-time)
        freshness = self.engine.calculate_data_freshness(
            market_data.get('timestamp', datetime.now())
        )
        
        # Stability from market history
        if market_history:
            stability = self.engine.calculate_volatility_stability(market_history)
        else:
            stability = 0.6
        
        return self.engine.calculate_signal_confidence(coverage, freshness, stability)

# =========================== CONFIDENCE-WEIGHTED SIGNAL PROCESSOR ===========================

class ConfidenceWeightedSignalProcessor:
    """
    Main processor that applies confidence weighting to all signals
    
    This is what prevents fake signals from garbage data.
    """
    
    def __init__(self):
        self.confidence_engine = ConfidenceEngine()
        self.valuation_calculator = ValuationConfidenceCalculator()
        self.macro_calculator = MacroConfidenceCalculator()
    
    def process_valuation_signal(self, valuation_result):
        """
        Process valuation signal with confidence weighting
        
        Input: Raw valuation z-score
        Output: Confidence-weighted effective signal
        """
        
        engine_type = valuation_result.get('engine_type', 'fundamental')
        raw_z_score = valuation_result.get('z_score', 0.0)
        
        # Calculate appropriate confidence
        if engine_type == 'fundamental':
            confidence_result = self.valuation_calculator.calculate_fundamental_confidence(
                valuation_result.get('data', {}),
                valuation_result.get('timestamp')
            )
        elif engine_type == 'macro_adjusted':
            confidence_result = self.valuation_calculator.calculate_macro_confidence(
                valuation_result.get('macro_data', {}),
                valuation_result.get('macro_history')
            )
        elif engine_type == 'relative':
            confidence_result = self.valuation_calculator.calculate_relative_confidence(
                valuation_result.get('relative_data', {}),
                valuation_result.get('sector_quality')
            )
        elif engine_type == 'market_implied':
            confidence_result = self.valuation_calculator.calculate_market_implied_confidence(
                valuation_result.get('market_data', {}),
                valuation_result.get('price_history')
            )
        else:
            # Default confidence calculation
            confidence_result = self.confidence_engine.calculate_signal_confidence(0.5, 0.5, 0.5)
        
        # Apply confidence to signal
        processed_signal = self.confidence_engine.apply_confidence_to_signal(
            raw_z_score, confidence_result
        )
        
        # Add valuation-specific metadata
        processed_signal.update({
            'engine_type': engine_type,
            'confidence_breakdown': confidence_result,
            'original_result': valuation_result
        })
        
        return processed_signal
    
    def process_macro_signal(self, macro_result):
        """Process macro signal with confidence weighting"""
        
        raw_score = macro_result.get('macro_score', 0.0)
        
        # Calculate macro confidence
        confidence_result = self.macro_calculator.calculate_rbi_data_confidence(
            macro_result.get('data', {}),
            macro_result.get('timestamp')
        )
        
        # Apply confidence
        processed_signal = self.confidence_engine.apply_confidence_to_signal(
            raw_score, confidence_result
        )
        
        processed_signal.update({
            'signal_type': 'macro',
            'confidence_breakdown': confidence_result,
            'original_result': macro_result
        })
        
        return processed_signal
    
    def process_opportunity_signal(self, opportunity_result):
        """Process opportunity surface signal with confidence weighting"""
        
        raw_mispricing = opportunity_result.get('mispricing', 0.0)
        
        # Calculate opportunity confidence based on data quality
        data_quality = opportunity_result.get('data_quality', {})
        
        coverage = data_quality.get('coverage', 0.5)
        freshness = data_quality.get('freshness', 0.5)
        stability = data_quality.get('stability', 0.5)
        
        confidence_result = self.confidence_engine.calculate_signal_confidence(
            coverage, freshness, stability
        )
        
        # Apply confidence
        processed_signal = self.confidence_engine.apply_confidence_to_signal(
            raw_mispricing, confidence_result
        )
        
        processed_signal.update({
            'signal_type': 'opportunity',
            'confidence_breakdown': confidence_result,
            'original_result': opportunity_result
        })
        
        return processed_signal
    
    def process_all_signals(self, signals_dict):
        """
        Process all signals with confidence weighting
        
        This is the main function that prevents fake signals across the entire system.
        """
        
        processed_signals = {}
        
        for signal_name, signal_data in signals_dict.items():
            try:
                if 'valuation' in signal_name.lower():
                    processed_signals[signal_name] = self.process_valuation_signal(signal_data)
                elif 'macro' in signal_name.lower():
                    processed_signals[signal_name] = self.process_macro_signal(signal_data)
                elif 'opportunity' in signal_name.lower():
                    processed_signals[signal_name] = self.process_opportunity_signal(signal_data)
                else:
                    # Generic signal processing
                    raw_value = signal_data.get('value', 0.0)
                    confidence_result = self.confidence_engine.calculate_signal_confidence(0.5, 0.5, 0.5)
                    processed_signals[signal_name] = self.confidence_engine.apply_confidence_to_signal(
                        raw_value, confidence_result
                    )
            except Exception as e:
                print(f"Error processing signal {signal_name}: {e}")
                continue
        
        return processed_signals

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate confidence engine functionality"""
    
    print("🎯 CONFIDENCE ENGINE - HEDGE FUND GRADE UNCERTAINTY QUANTIFICATION")
    print("=" * 80)
    
    # Initialize engines
    confidence_engine = ConfidenceEngine()
    processor = ConfidenceWeightedSignalProcessor()
    
    # Example 1: Basic confidence calculation
    print("\n📊 Example 1: Basic Confidence Calculation")
    print("-" * 50)
    
    confidence_result = confidence_engine.calculate_signal_confidence(
        data_coverage=0.6,      # 60% of required data available
        data_freshness=0.7,     # Data is 1 week old
        volatility_stability=0.5 # Moderate signal stability
    )
    
    print(f"Overall Confidence: {confidence_result['overall_confidence']:.3f}")
    print(f"Confidence Grade: {confidence_result['grade']}")
    print(f"Components: {confidence_result['components']}")
    
    # Example 2: Apply confidence to signal
    print("\n🎯 Example 2: Confidence-Weighted Signal")
    print("-" * 50)
    
    raw_signal = -1.8  # Strong undervaluation signal
    adjusted_signal = confidence_engine.apply_confidence_to_signal(raw_signal, confidence_result)
    
    print(f"Raw Signal: {adjusted_signal['raw_signal']:.2f}")
    print(f"Effective Signal: {adjusted_signal['effective_signal']:.2f}")
    print(f"Confidence: {adjusted_signal['confidence']:.3f}")
    print(f"Reliability: {adjusted_signal['reliability']}")
    print(f"Actionable: {adjusted_signal['actionable']}")
    
    # Example 3: Valuation confidence
    print("\n💰 Example 3: Valuation Signal Confidence")
    print("-" * 50)
    
    valuation_data = {
        'engine_type': 'fundamental',
        'z_score': -1.5,
        'data': {
            'pe_ratio': 15.2,
            'pb_ratio': 2.1,
            'roe': 18.5,
            'debt_equity': 0.3
        },
        'timestamp': datetime.now() - timedelta(days=2)
    }
    
    processed_valuation = processor.process_valuation_signal(valuation_data)
    
    print(f"Raw Valuation Z-Score: {processed_valuation['raw_signal']:.2f}")
    print(f"Effective Z-Score: {processed_valuation['effective_signal']:.2f}")
    print(f"Confidence Grade: {processed_valuation['confidence_grade']}")
    print(f"Actionable: {processed_valuation['actionable']}")
    
    print("\n✅ Confidence engine operational - preventing fake signals from garbage data")

if __name__ == "__main__":
    main()