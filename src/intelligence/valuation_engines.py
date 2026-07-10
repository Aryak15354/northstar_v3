#!/usr/bin/env python3
"""
🧠 VALUATION ENGINES - 4 INDEPENDENT BRAINS
Institutional-Grade Valuation Intelligence for Northstar V3

This splits "mispricing" into 4 separate valuation brains:
1. Fundamental Value - Is the company cheap vs earnings, assets, cashflows?
2. Macro-adjusted Value - Is it cheap given interest rates, inflation, liquidity?
3. Relative Value - Is it cheap vs its sector & peers?
4. Market-implied Value - What valuation is the market pricing in?

Each engine gives a z-score (cheap → expensive).
Each engine has confidence weighting.

Usage:
    try:
    from src.intelligence.valuation_engines import ValuationEngineStack
except ImportError:
    from ValuationEngineStack import ValuationEngineStack
    
    engines = ValuationEngineStack()
    valuations = engines.compute_all_valuations(ticker='RELIANCE')
    
    # Result: 4 independent z-scores with confidence
    fundamental_z = valuations['fundamental']['z_score']
    confidence = valuations['fundamental']['confidence']
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

# Temporal protection
try:
    from src.intelligence.temporal_signal_engine import TemporalSignalEngine
except ImportError:
    from TemporalSignalEngine import TemporalSignalEngine
except ImportError:
    from temporal_signal_engine import TemporalSignalEngine

# =========================== VALUATION ENGINE SCHEMA ===========================

VALUATION_SCHEMA = {
    'ticker': 'string',
    'date': 'datetime64[ns]',
    'fundamental_z': 'float64',
    'fundamental_confidence': 'float64',
    'macro_adjusted_z': 'float64', 
    'macro_confidence': 'float64',
    'relative_z': 'float64',
    'relative_confidence': 'float64',
    'market_implied_z': 'float64',
    'implied_confidence': 'float64',
    'composite_z': 'float64',
    'composite_confidence': 'float64'
}

# =========================== FUNDAMENTAL VALUE ENGINE ===========================

class FundamentalValueEngine:
    """
    Engine 1: Fundamental Value
    Question: Is the company cheap vs earnings, assets, cashflows?
    
    Uses: P/E, P/B, P/S, EV/EBITDA, FCF Yield, ROE, Debt/Equity
    Output: Z-score (-2 = very cheap, +2 = very expensive)
    """
    
    def __init__(self):
        self.name = "Fundamental Value"
        self.data_sources = [
            'data/processed/fundamentals.parquet',
            'data/processed/scores.parquet',
            'data/raw/financials'
        ]
    
    def safe_read_data(self, ticker):
        """Safely read fundamental data for ticker"""
        
        # Try processed fundamentals first
        try:
            fund_path = 'data/processed/fundamentals.parquet'
            if os.path.exists(fund_path):
                df = pd.read_parquet(fund_path)
                if not df.empty and ticker in df['ticker'].values:
                    return df[df['ticker'] == ticker].iloc[-1]  # most recent row for this ticker
        except Exception as e:
            pass
        
        # Try scores data as fallback
        try:
            scores_path = 'data/processed/scores.parquet'
            if os.path.exists(scores_path):
                df = pd.read_parquet(scores_path)
                if not df.empty and ticker in df['ticker'].values:
                    return df[df['ticker'] == ticker].iloc[-1]  # most recent row for this ticker
        except Exception as e:
            pass
        
        return None
    
    def calculate_pe_zscore(self, pe_ratio, sector_pe_median=20):
        """Calculate P/E z-score vs sector"""
        if pd.isna(pe_ratio) or pe_ratio <= 0:
            return 0.0, 0.3  # Neutral with low confidence
        
        # Log-normalize P/E for better distribution
        log_pe = np.log(pe_ratio)
        log_sector_median = np.log(sector_pe_median)
        
        # Assume sector P/E std of 0.5 in log space
        z_score = (log_pe - log_sector_median) / 0.5
        
        # Confidence based on data quality
        confidence = 0.8 if pe_ratio > 0 and pe_ratio < 100 else 0.5
        
        return -z_score, confidence  # Negative because high P/E = expensive
    
    def calculate_pb_zscore(self, pb_ratio, sector_pb_median=3.0):
        """Calculate P/B z-score vs sector"""
        if pd.isna(pb_ratio) or pb_ratio <= 0:
            return 0.0, 0.3
        
        log_pb = np.log(pb_ratio)
        log_sector_median = np.log(sector_pb_median)
        
        z_score = (log_pb - log_sector_median) / 0.4
        confidence = 0.7 if pb_ratio > 0 and pb_ratio < 10 else 0.4
        
        return -z_score, confidence
    
    def calculate_roe_zscore(self, roe, sector_roe_median=15):
        """Calculate ROE z-score vs sector"""
        if pd.isna(roe):
            return 0.0, 0.3
        
        # ROE z-score (higher ROE = better value)
        z_score = (roe - sector_roe_median) / 10  # Assume 10% std
        confidence = 0.8 if abs(roe) < 50 else 0.5
        
        return z_score, confidence  # Positive because high ROE = good value
    
    def calculate_debt_zscore(self, debt_equity, sector_de_median=0.5):
        """Calculate Debt/Equity z-score vs sector"""
        if pd.isna(debt_equity):
            return 0.0, 0.3
        
        # Lower debt = better (safer value)
        z_score = -(debt_equity - sector_de_median) / 0.3
        confidence = 0.7 if debt_equity >= 0 and debt_equity < 2 else 0.4
        
        return z_score, confidence
    
    def compute_fundamental_value(self, ticker):
        """
        Compute fundamental value z-score
        
        Returns:
            dict: {
                'z_score': float,
                'confidence': float,
                'components': dict,
                'data_coverage': float
            }
        """
        
        data = self.safe_read_data(ticker)
        if data is None:
            return {
                'z_score': 0.0,
                'confidence': 0.2,
                'components': {},
                'data_coverage': 0.0,
                'status': 'no_data'
            }
        
        components = {}
        z_scores = []
        confidences = []
        
        # P/E Analysis
        pe_ratio = data.get('pe_ratio') or data.get('PE') or data.get('price_earnings')
        if pe_ratio and not pd.isna(pe_ratio):
            pe_z, pe_conf = self.calculate_pe_zscore(pe_ratio)
            components['pe'] = {'z_score': pe_z, 'confidence': pe_conf, 'value': pe_ratio}
            z_scores.append(pe_z)
            confidences.append(pe_conf)
        
        # P/B Analysis
        pb_ratio = data.get('pb_ratio') or data.get('PB') or data.get('price_book')
        if pb_ratio and not pd.isna(pb_ratio):
            pb_z, pb_conf = self.calculate_pb_zscore(pb_ratio)
            components['pb'] = {'z_score': pb_z, 'confidence': pb_conf, 'value': pb_ratio}
            z_scores.append(pb_z)
            confidences.append(pb_conf)
        
        # ROE Analysis
        roe = data.get('roe') or data.get('ROE') or data.get('return_on_equity')
        if roe and not pd.isna(roe):
            roe_z, roe_conf = self.calculate_roe_zscore(roe)
            components['roe'] = {'z_score': roe_z, 'confidence': roe_conf, 'value': roe}
            z_scores.append(roe_z)
            confidences.append(roe_conf)
        
        # Debt/Equity Analysis
        debt_equity = data.get('debt_equity') or data.get('DE') or data.get('debt_to_equity')
        if debt_equity and not pd.isna(debt_equity):
            de_z, de_conf = self.calculate_debt_zscore(debt_equity)
            components['debt_equity'] = {'z_score': de_z, 'confidence': de_conf, 'value': debt_equity}
            z_scores.append(de_z)
            confidences.append(de_conf)
        
        # Composite calculation
        if z_scores:
            # Weighted average by confidence
            weights = np.array(confidences)
            weighted_z = np.average(z_scores, weights=weights)
            avg_confidence = np.mean(confidences)
            data_coverage = len(z_scores) / 4  # 4 expected metrics
        else:
            weighted_z = 0.0
            avg_confidence = 0.2
            data_coverage = 0.0
        
        return {
            'z_score': float(weighted_z),
            'confidence': float(avg_confidence),
            'components': components,
            'data_coverage': data_coverage,
            'status': 'active' if data_coverage > 0.5 else 'partial'
        }

# =========================== MACRO-ADJUSTED VALUE ENGINE ===========================

class MacroAdjustedValueEngine:
    """
    Engine 2: Macro-adjusted Value
    Question: Is it cheap given interest rates, inflation, liquidity?
    
    Adjusts fundamental value for macro environment:
    - High rates → lower fair P/E
    - High inflation → sector-specific impacts
    - Tight liquidity → discount to fair value
    """
    
    def __init__(self):
        self.name = "Macro-adjusted Value"
        self.macro_data_path = 'data/macro/factors/macro_score.parquet'
    
    def load_macro_state(self):
        """Load current macro environment"""
        try:
            if os.path.exists(self.macro_data_path):
                df = pd.read_parquet(self.macro_data_path)
                if not df.empty:
                    latest = df.iloc[-1]  # most recent macro reading
                    return {
                        'macro_score': latest.get('MacroScore', 0.0),
                        'growth': latest.get('Contrib_G', 0.0),
                        'inflation': latest.get('Contrib_I', 0.0),
                        'liquidity': latest.get('Contrib_L', 0.0),
                        'stress': latest.get('Contrib_S', 0.0),
                        'confidence': 0.8
                    }
        except Exception as e:
            pass
        
        # Default neutral macro state
        return {
            'macro_score': 0.0,
            'growth': 0.0,
            'inflation': 0.0,
            'liquidity': 0.0,
            'stress': 0.0,
            'confidence': 0.3
        }
    
    def calculate_rate_adjustment(self, fundamental_z, liquidity_score):
        """Adjust valuation for interest rate environment"""
        
        # High liquidity (low rates) → premium to fair value
        # Low liquidity (high rates) → discount to fair value
        rate_adjustment = liquidity_score * 0.5  # ±0.5 z-score adjustment
        
        adjusted_z = fundamental_z + rate_adjustment
        confidence = 0.7 if abs(liquidity_score) > 0.2 else 0.5
        
        return adjusted_z, confidence
    
    def calculate_inflation_adjustment(self, fundamental_z, inflation_score, sector):
        """Adjust valuation for inflation environment"""
        
        # Sector-specific inflation sensitivity
        inflation_sensitive_sectors = ['FMCG', 'Auto', 'Metal']  # Benefit from inflation
        inflation_resistant_sectors = ['IT', 'Pharma']  # Hurt by inflation
        
        if sector in inflation_sensitive_sectors:
            # These sectors benefit from inflation
            inflation_adjustment = inflation_score * 0.3
        elif sector in inflation_resistant_sectors:
            # These sectors are hurt by inflation
            inflation_adjustment = -inflation_score * 0.3
        else:
            # Neutral impact
            inflation_adjustment = 0.0
        
        adjusted_z = fundamental_z + inflation_adjustment
        confidence = 0.6 if abs(inflation_score) > 0.2 else 0.4
        
        return adjusted_z, confidence
    
    def calculate_growth_adjustment(self, fundamental_z, growth_score):
        """Adjust valuation for growth environment"""
        
        # High growth → can pay premium for quality
        # Low growth → need discount for safety
        growth_adjustment = growth_score * 0.4
        
        adjusted_z = fundamental_z + growth_adjustment
        confidence = 0.7 if abs(growth_score) > 0.3 else 0.5
        
        return adjusted_z, confidence
    
    def compute_macro_adjusted_value(self, ticker, fundamental_result):
        """
        Compute macro-adjusted value z-score
        
        Takes fundamental value and adjusts for macro environment
        """
        
        if fundamental_result['status'] == 'no_data':
            return {
                'z_score': 0.0,
                'confidence': 0.2,
                'adjustments': {},
                'status': 'no_fundamental_data'
            }
        
        macro_state = self.load_macro_state()
        fundamental_z = fundamental_result['z_score']
        
        # Get sector (simplified - would normally look up)
        sector = 'Other'  # Default
        
        adjustments = {}
        
        # Rate adjustment
        rate_adj_z, rate_conf = self.calculate_rate_adjustment(
            fundamental_z, macro_state['liquidity']
        )
        adjustments['rates'] = {
            'adjustment': rate_adj_z - fundamental_z,
            'confidence': rate_conf,
            'liquidity_score': macro_state['liquidity']
        }
        
        # Inflation adjustment
        inflation_adj_z, inflation_conf = self.calculate_inflation_adjustment(
            rate_adj_z, macro_state['inflation'], sector
        )
        adjustments['inflation'] = {
            'adjustment': inflation_adj_z - rate_adj_z,
            'confidence': inflation_conf,
            'inflation_score': macro_state['inflation']
        }
        
        # Growth adjustment
        final_z, growth_conf = self.calculate_growth_adjustment(
            inflation_adj_z, macro_state['growth']
        )
        adjustments['growth'] = {
            'adjustment': final_z - inflation_adj_z,
            'confidence': growth_conf,
            'growth_score': macro_state['growth']
        }
        
        # Overall confidence
        macro_confidence = macro_state['confidence']
        fundamental_confidence = fundamental_result['confidence']
        
        # Combined confidence (minimum of macro and fundamental)
        combined_confidence = min(macro_confidence, fundamental_confidence) * 0.9
        
        return {
            'z_score': float(final_z),
            'confidence': float(combined_confidence),
            'adjustments': adjustments,
            'macro_state': macro_state,
            'status': 'active'
        }

# =========================== RELATIVE VALUE ENGINE ===========================

class RelativeValueEngine:
    """
    Engine 3: Relative Value
    Question: Is it cheap vs its sector & peers?
    
    Compares stock to:
    - Sector median P/E, P/B, ROE
    - Peer group averages
    - Historical relative performance
    """
    
    def __init__(self):
        self.name = "Relative Value"
        self.scores_path = 'data/processed/scores.parquet'
    
    def load_universe_data(self):
        """Load universe data for relative comparisons"""
        try:
            if os.path.exists(self.scores_path):
                df = pd.read_parquet(self.scores_path)
                if not df.empty:
                    return df
        except Exception as e:
            pass
        
        return pd.DataFrame()
    
    def get_sector_stats(self, universe_df, sector):
        """Calculate sector statistics"""
        if universe_df.empty:
            return None
        
        # Filter by sector (simplified - would use proper sector mapping)
        sector_df = universe_df  # For now, use full universe
        
        stats = {}
        
        # P/E statistics
        pe_col = None
        for col in ['pe_ratio', 'PE', 'price_earnings']:
            if col in sector_df.columns:
                pe_col = col
                break
        
        if pe_col:
            pe_data = sector_df[pe_col].dropna()
            pe_data = pe_data[(pe_data > 0) & (pe_data < 100)]  # Filter outliers
            if not pe_data.empty:
                stats['pe_median'] = pe_data.median()
                stats['pe_std'] = pe_data.std()
        
        # P/B statistics
        pb_col = None
        for col in ['pb_ratio', 'PB', 'price_book']:
            if col in sector_df.columns:
                pb_col = col
                break
        
        if pb_col:
            pb_data = sector_df[pb_col].dropna()
            pb_data = pb_data[(pb_data > 0) & (pb_data < 20)]  # Filter outliers
            if not pb_data.empty:
                stats['pb_median'] = pb_data.median()
                stats['pb_std'] = pb_data.std()
        
        return stats if stats else None
    
    def calculate_relative_pe(self, pe_ratio, sector_stats):
        """Calculate relative P/E z-score"""
        if not sector_stats or 'pe_median' not in sector_stats:
            return 0.0, 0.3
        
        if pd.isna(pe_ratio) or pe_ratio <= 0:
            return 0.0, 0.3
        
        sector_median = sector_stats['pe_median']
        sector_std = sector_stats.get('pe_std', sector_median * 0.3)
        
        # Z-score vs sector
        z_score = (pe_ratio - sector_median) / sector_std
        confidence = 0.8
        
        return -z_score, confidence  # Negative because high P/E = expensive
    
    def calculate_relative_pb(self, pb_ratio, sector_stats):
        """Calculate relative P/B z-score"""
        if not sector_stats or 'pb_median' not in sector_stats:
            return 0.0, 0.3
        
        if pd.isna(pb_ratio) or pb_ratio <= 0:
            return 0.0, 0.3
        
        sector_median = sector_stats['pb_median']
        sector_std = sector_stats.get('pb_std', sector_median * 0.3)
        
        z_score = (pb_ratio - sector_median) / sector_std
        confidence = 0.7
        
        return -z_score, confidence
    
    def compute_relative_value(self, ticker, fundamental_result):
        """
        Compute relative value z-score vs sector and peers
        """
        
        if fundamental_result['status'] == 'no_data':
            return {
                'z_score': 0.0,
                'confidence': 0.2,
                'comparisons': {},
                'status': 'no_data'
            }
        
        universe_df = self.load_universe_data()
        if universe_df.empty:
            return {
                'z_score': 0.0,
                'confidence': 0.3,
                'comparisons': {},
                'status': 'no_universe_data'
            }
        
        # Get stock data
        stock_data = universe_df[universe_df['ticker'] == ticker]
        if stock_data.empty:
            return {
                'z_score': 0.0,
                'confidence': 0.2,
                'comparisons': {},
                'status': 'stock_not_found'
            }
        
        stock_row = stock_data.iloc[0]
        
        # Get sector (simplified)
        sector = 'Other'
        sector_stats = self.get_sector_stats(universe_df, sector)
        
        if not sector_stats:
            return {
                'z_score': 0.0,
                'confidence': 0.3,
                'comparisons': {},
                'status': 'no_sector_data'
            }
        
        comparisons = {}
        z_scores = []
        confidences = []
        
        # Relative P/E
        pe_ratio = stock_row.get('pe_ratio') or stock_row.get('PE')
        if pe_ratio and not pd.isna(pe_ratio):
            pe_z, pe_conf = self.calculate_relative_pe(pe_ratio, sector_stats)
            comparisons['pe_relative'] = {
                'z_score': pe_z,
                'confidence': pe_conf,
                'stock_value': pe_ratio,
                'sector_median': sector_stats.get('pe_median')
            }
            z_scores.append(pe_z)
            confidences.append(pe_conf)
        
        # Relative P/B
        pb_ratio = stock_row.get('pb_ratio') or stock_row.get('PB')
        if pb_ratio and not pd.isna(pb_ratio):
            pb_z, pb_conf = self.calculate_relative_pb(pb_ratio, sector_stats)
            comparisons['pb_relative'] = {
                'z_score': pb_z,
                'confidence': pb_conf,
                'stock_value': pb_ratio,
                'sector_median': sector_stats.get('pb_median')
            }
            z_scores.append(pb_z)
            confidences.append(pb_conf)
        
        # Composite relative value
        if z_scores:
            weights = np.array(confidences)
            weighted_z = np.average(z_scores, weights=weights)
            avg_confidence = np.mean(confidences)
        else:
            weighted_z = 0.0
            avg_confidence = 0.3
        
        return {
            'z_score': float(weighted_z),
            'confidence': float(avg_confidence),
            'comparisons': comparisons,
            'sector_stats': sector_stats,
            'status': 'active' if z_scores else 'insufficient_data'
        }

# =========================== MARKET-IMPLIED VALUE ENGINE ===========================

class MarketImpliedValueEngine:
    """
    Engine 4: Market-implied Value
    Question: What valuation is the market pricing in?
    
    Uses:
    - Options implied volatility
    - Analyst price targets
    - Recent price momentum
    - Market cap vs fundamentals
    """
    
    def __init__(self):
        self.name = "Market-implied Value"
        self.options_path = 'data/options/live'
        self.prices_path = 'data/raw/prices_daily'
    
    def load_price_data(self, ticker):
        """Load recent price data for momentum analysis"""
        try:
            price_file = os.path.join(self.prices_path, f'{ticker}.NS.csv')
            if not os.path.exists(price_file):
                price_file = os.path.join(self.prices_path, f'{ticker}.csv')
            
            if os.path.exists(price_file):
                df = self.signal_engine.guard.get_data(price_file)
                if not df.empty and 'Close' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.sort_values('Date')
                    return df.tail(60)  # Last 60 days
        except Exception as e:
            pass
        
        return pd.DataFrame()
    
    def calculate_momentum_zscore(self, price_df):
        """Calculate momentum-based valuation signal"""
        if price_df.empty or len(price_df) < 20:
            return 0.0, 0.3
        
        # Calculate returns
        price_df = price_df.copy()
        price_df['returns'] = price_df['Close'].pct_change()
        
        # Recent performance vs historical - TEMPORAL PROTECTED
        recent_return = (price_df['Close'].iloc[-1] / price_df['Close'].iloc[-20] - 1) * 100  # 20-day return
        historical_vol = price_df['returns'].std() * np.sqrt(252) * 100  # Annualized vol
        
        if historical_vol == 0:
            return 0.0, 0.3
        
        # Momentum z-score (high momentum suggests market expects higher value)
        momentum_z = recent_return / (historical_vol / 4)  # Normalize by quarterly vol
        
        # Confidence based on data quality
        confidence = 0.6 if len(price_df) >= 40 else 0.4
        
        return momentum_z, confidence
    
    def calculate_volatility_signal(self, ticker):
        """Calculate implied volatility signal (if options data available)"""
        
        # Try to load options data
        try:
            options_file = os.path.join(self.options_path, 'options_data_latest.json')
            if os.path.exists(options_file):
                import json
                with open(options_file, 'r') as f:
                    options_data = json.load(f)
                
                # Look for ticker in options data
                if ticker in options_data:
                    # Simplified IV analysis
                    iv_data = options_data[ticker]
                    # This would be more sophisticated in practice
                    return 0.0, 0.5  # Placeholder
        except Exception as e:
            pass
        
        return 0.0, 0.3  # No options data available
    
    def calculate_price_target_signal(self, ticker, current_price):
        """Calculate analyst price target signal (if available)"""
        
        # This would integrate with analyst data feeds
        # For now, return neutral
        return 0.0, 0.3
    
    def compute_market_implied_value(self, ticker):
        """
        Compute market-implied value z-score
        
        What valuation is the market pricing in based on:
        - Price momentum
        - Options implied volatility
        - Analyst targets
        """
        
        price_df = self.load_price_data(ticker)
        
        if price_df.empty:
            return {
                'z_score': 0.0,
                'confidence': 0.2,
                'signals': {},
                'status': 'no_price_data'
            }
        
        current_price = price_df['Close'].iloc[-1]  # most recent close
        
        signals = {}
        z_scores = []
        confidences = []
        
        # Momentum signal
        momentum_z, momentum_conf = self.calculate_momentum_zscore(price_df)
        signals['momentum'] = {
            'z_score': momentum_z,
            'confidence': momentum_conf,
            'description': 'Recent price momentum vs historical volatility'
        }
        z_scores.append(momentum_z)
        confidences.append(momentum_conf)
        
        # Volatility signal
        iv_z, iv_conf = self.calculate_volatility_signal(ticker)
        if iv_conf > 0.4:  # Only include if we have decent IV data
            signals['implied_volatility'] = {
                'z_score': iv_z,
                'confidence': iv_conf,
                'description': 'Options implied volatility signal'
            }
            z_scores.append(iv_z)
            confidences.append(iv_conf)
        
        # Price target signal
        target_z, target_conf = self.calculate_price_target_signal(ticker, current_price)
        if target_conf > 0.4:  # Only include if we have analyst data
            signals['price_targets'] = {
                'z_score': target_z,
                'confidence': target_conf,
                'description': 'Analyst price target signal'
            }
            z_scores.append(target_z)
            confidences.append(target_conf)
        
        # Composite market-implied value
        if z_scores:
            weights = np.array(confidences)
            weighted_z = np.average(z_scores, weights=weights)
            avg_confidence = np.mean(confidences)
        else:
            weighted_z = 0.0
            avg_confidence = 0.3
        
        return {
            'z_score': float(weighted_z),
            'confidence': float(avg_confidence),
            'signals': signals,
            'current_price': current_price,
            'status': 'active' if z_scores else 'limited_data'
        }

# =========================== VALUATION ENGINE STACK ===========================

class ValuationEngineStack:
    """
    Master class that orchestrates all 4 valuation engines
    
    This is what hedge funds actually do - they don't rely on one valuation metric.
    They run multiple independent valuation models and synthesize the results.
    """
    
    def __init__(self):
        self.engines = {
            'fundamental': FundamentalValueEngine(),
            'macro_adjusted': MacroAdjustedValueEngine(),
            'relative': RelativeValueEngine(),
            'market_implied': MarketImpliedValueEngine()
        }
        
        self.output_path = 'data/processed/valuation_engines.parquet'
    
    def compute_all_valuations(self, ticker):
        """
        Run all 4 valuation engines for a ticker
        
        Returns comprehensive valuation analysis with confidence weighting
        """
        
        print(f"🧠 Running 4 valuation engines for {ticker}...")
        
        results = {
            'ticker': ticker,
            'date': datetime.now(),
            'engines': {}
        }
        
        # Engine 1: Fundamental Value
        fundamental_result = self.engines['fundamental'].compute_fundamental_value(ticker)
        results['engines']['fundamental'] = fundamental_result
        
        # Engine 2: Macro-adjusted Value (uses fundamental as input)
        macro_result = self.engines['macro_adjusted'].compute_macro_adjusted_value(ticker, fundamental_result)
        results['engines']['macro_adjusted'] = macro_result
        
        # Engine 3: Relative Value (uses fundamental as input)
        relative_result = self.engines['relative'].compute_relative_value(ticker, fundamental_result)
        results['engines']['relative'] = relative_result
        
        # Engine 4: Market-implied Value (independent)
        implied_result = self.engines['market_implied'].compute_market_implied_value(ticker)
        results['engines']['market_implied'] = implied_result
        
        # Synthesize results
        synthesis = self.synthesize_valuations(results)
        results['synthesis'] = synthesis
        
        return results
    
    def synthesize_valuations(self, results):
        """
        Synthesize all 4 engines into final valuation assessment
        
        This is where the magic happens - combining 4 independent views
        """
        
        engines = results['engines']
        
        # Extract z-scores and confidences
        z_scores = []
        confidences = []
        engine_names = []
        
        for name, engine_result in engines.items():
            if engine_result.get('status') in ['active', 'partial']:
                z_score = engine_result.get('z_score', 0.0)
                confidence = engine_result.get('confidence', 0.3)
                
                z_scores.append(z_score)
                confidences.append(confidence)
                engine_names.append(name)
        
        if not z_scores:
            return {
                'composite_z_score': 0.0,
                'composite_confidence': 0.2,
                'agreement': 0.0,
                'narrative': 'Insufficient data for valuation assessment',
                'status': 'no_data'
            }
        
        # Weighted composite z-score
        weights = np.array(confidences)
        composite_z = np.average(z_scores, weights=weights)
        composite_confidence = np.mean(confidences)
        
        # Calculate agreement between engines
        if len(z_scores) > 1:
            # Agreement = 1 - (std of z-scores / mean absolute z-score)
            z_std = np.std(z_scores)
            z_mean_abs = np.mean(np.abs(z_scores))
            agreement = max(0, 1 - (z_std / (z_mean_abs + 0.5)))
        else:
            agreement = 1.0
        
        # Generate narrative
        narrative = self.generate_valuation_narrative(z_scores, confidences, engine_names, agreement)
        
        # Final confidence adjustment for agreement
        final_confidence = composite_confidence * (0.5 + 0.5 * agreement)
        
        return {
            'composite_z_score': float(composite_z),
            'composite_confidence': float(final_confidence),
            'agreement': float(agreement),
            'narrative': narrative,
            'engine_count': len(z_scores),
            'individual_scores': dict(zip(engine_names, z_scores)),
            'individual_confidences': dict(zip(engine_names, confidences)),
            'status': 'high_conviction' if final_confidence > 0.7 else 'moderate' if final_confidence > 0.5 else 'low_conviction'
        }
    
    def generate_valuation_narrative(self, z_scores, confidences, engine_names, agreement):
        """Generate human-readable valuation narrative"""
        
        composite_z = np.average(z_scores, weights=confidences)
        
        # Overall valuation assessment
        if composite_z > 1.5:
            valuation_view = "significantly undervalued"
        elif composite_z > 0.5:
            valuation_view = "undervalued"
        elif composite_z > -0.5:
            valuation_view = "fairly valued"
        elif composite_z > -1.5:
            valuation_view = "overvalued"
        else:
            valuation_view = "significantly overvalued"
        
        # Agreement assessment
        if agreement > 0.8:
            agreement_text = "Strong consensus"
        elif agreement > 0.6:
            agreement_text = "Moderate agreement"
        else:
            agreement_text = "Mixed signals"
        
        # Engine breakdown
        engine_summary = []
        for name, z_score in zip(engine_names, z_scores):
            if z_score > 0.5:
                engine_summary.append(f"{name}: cheap")
            elif z_score < -0.5:
                engine_summary.append(f"{name}: expensive")
            else:
                engine_summary.append(f"{name}: neutral")
        
        narrative = f"{agreement_text} - Stock appears {valuation_view}. "
        narrative += f"Engines: {', '.join(engine_summary)}."
        
        return narrative
    
    def compute_universe_valuations(self, tickers=None):
        """
        Compute valuations for the entire universe, VECTORIZED, from the
        already-computed per-industry valuation surface (data/processed/
        valuation.parquet).

        Why this replaced the old per-ticker loop: the previous implementation
        called compute_all_valuations() -> each engine's safe_read_data(), which
        read data/processed/fundamentals.parquet / scores.parquet. Those files
        carry NO pe/pb/roe/debt ratio columns, so every ratio lookup missed,
        every engine fell through to its neutral default, and the entire 497-name
        output collapsed to a single universe-wide constant (composite_z =
        0.164677 for every stock, identical "fairly valued" narrative) — an
        authoritative-looking table with zero stock-specific information. It also
        used hard-coded universal anchors (P/E median 20 for every sector) and a
        percent-vs-fraction ROE unit mismatch.

        valuation.parquet already contains sector-aware, per-industry percentile
        ranks and composite scores (institutional_value_score,
        buffett_quality_score, margin_of_safety, pe_pct/pb_pct/ev_ebitda_pct).
        We map the four "brains" onto four genuinely distinct, real, per-stock
        signals and cross-sectionally standardize each, so the output varies per
        stock (guarded by scripts/ci/check_live_artifact_invariants.py:
        valuation_engines_nondegenerate).

        Convention (matches main()): composite_z > 0 = undervalued/cheap.
        """
        val_path = 'data/processed/valuation.parquet'
        if not os.path.exists(val_path):
            print(f"❌ {val_path} missing — cannot compute valuations")
            return pd.DataFrame()
        val = pd.read_parquet(val_path)
        if val.empty:
            print("❌ valuation.parquet is empty")
            return pd.DataFrame()
        if 'date' in val.columns:
            val = val.sort_values('date').groupby('ticker', as_index=False).tail(1)
        val = val.reset_index(drop=True)

        if tickers is not None:
            want = {str(t) for t in tickers}
            tk = val['ticker'].astype(str)
            val = val[tk.isin(want)
                      | (tk + '.NS').isin(want)
                      | tk.str.replace('.NS', '', regex=False).isin(want)].reset_index(drop=True)
        if val.empty:
            print("❌ No valuation rows after ticker filter")
            return pd.DataFrame()

        print(f"🧠 Computing valuations for {len(val)} stocks (vectorized from valuation surface)...")

        def zc(col: str) -> pd.Series:
            """Cross-sectional z-score of a real signal, NaN->median, clipped."""
            s = pd.to_numeric(val.get(col), errors='coerce')
            s = s.fillna(s.median())
            mu, sd = s.mean(), s.std(ddof=0)
            if not np.isfinite(sd) or sd < 1e-9:
                return pd.Series(0.0, index=val.index)
            return ((s - mu) / sd).clip(-3.0, 3.0)

        # Sector-relative cheapness (low valuation percentile within industry = cheap).
        val['_rel_base'] = (
            (1.0 - pd.to_numeric(val.get('pe_pct'), errors='coerce'))
            + (1.0 - pd.to_numeric(val.get('pb_pct'), errors='coerce'))
            + (1.0 - pd.to_numeric(val.get('ev_ebitda_pct'), errors='coerce'))
        ) / 3.0

        out = pd.DataFrame({'ticker': val['ticker'].astype(str).values})
        out['date'] = pd.Timestamp.now()
        # Four distinct real brains:
        out['fundamental_z'] = zc('institutional_value_score').values   # cheapness + quality composite
        out['macro_adjusted_z'] = zc('buffett_quality_score').values    # durability / macro-resilient quality
        out['relative_z'] = zc('_rel_base').values                      # cheap vs sector peers
        out['market_implied_z'] = zc('margin_of_safety').values         # intrinsic vs market price

        cov_cols = ['institutional_value_score', 'buffett_quality_score', '_rel_base', 'margin_of_safety']
        coverage = val[cov_cols].apply(lambda c: pd.to_numeric(c, errors='coerce')).notna().mean(axis=1).to_numpy()
        base_conf = 0.4 + 0.5 * coverage
        out['fundamental_confidence'] = base_conf
        out['macro_confidence'] = base_conf
        out['relative_confidence'] = base_conf
        out['implied_confidence'] = base_conf

        zmat = out[['fundamental_z', 'macro_adjusted_z', 'relative_z', 'market_implied_z']].to_numpy(float)
        cmat = out[['fundamental_confidence', 'macro_confidence', 'relative_confidence', 'implied_confidence']].to_numpy(float)
        wsum = cmat.sum(axis=1)
        composite = (zmat * cmat).sum(axis=1) / np.where(wsum > 0, wsum, 1.0)
        out['composite_z'] = composite
        out['composite_confidence'] = cmat.mean(axis=1)
        zstd = zmat.std(axis=1)
        zmabs = np.abs(zmat).mean(axis=1)
        out['agreement'] = np.clip(1.0 - zstd / (zmabs + 0.5), 0.0, 1.0)

        def _narrative(z: float) -> str:
            if z > 0.75:
                lvl = 'materially undervalued'
            elif z > 0.25:
                lvl = 'modestly undervalued'
            elif z < -0.75:
                lvl = 'materially overvalued'
            elif z < -0.25:
                lvl = 'modestly overvalued'
            else:
                lvl = 'fairly valued'
            return (f"Composite z={z:+.2f}: {lvl} vs sector on fundamentals, "
                    f"quality, relative multiples and intrinsic value.")

        out['narrative'] = [_narrative(z) for z in composite]

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        out.to_parquet(self.output_path, index=False)
        print(f"💾 Saved {len(out)} valuations to {self.output_path} "
              f"(composite_z std={float(np.std(composite)):.3f})")
        return out
    
    def load_latest_valuations(self):
        """Load latest valuation results"""
        try:
            if os.path.exists(self.output_path):
                df = pd.read_parquet(self.output_path)
                if not df.empty:
                    return df
        except Exception as e:
            print(f"Error loading valuations: {e}")
        
        return pd.DataFrame()

# =========================== MAIN EXECUTION ===========================

def main():
    """Main execution - compute valuations for universe"""
    
    print("🧠 VALUATION ENGINES - 4 INDEPENDENT BRAINS")
    print("=" * 60)
    
    # Initialize engine stack
    engines = ValuationEngineStack()
    
    # Compute valuations for universe
    results_df = engines.compute_universe_valuations()
    
    if not results_df.empty:
        print("\n📊 VALUATION SUMMARY")
        print("-" * 40)
        print(f"Stocks analyzed: {len(results_df)}")
        print(f"Average composite confidence: {results_df['composite_confidence'].mean():.2f}")
        print(f"Undervalued stocks (z > 0.5): {len(results_df[results_df['composite_z'] > 0.5])}")
        print(f"Overvalued stocks (z < -0.5): {len(results_df[results_df['composite_z'] < -0.5])}")
        
        # Top undervalued
        undervalued = results_df[results_df['composite_z'] > 0.5].nlargest(5, 'composite_z')
        if not undervalued.empty:
            print("\n🟢 TOP UNDERVALUED:")
            for _, row in undervalued.iterrows():
                print(f"  {row['ticker']}: z={row['composite_z']:.2f}, conf={row['composite_confidence']:.2f}")
        
        # Top overvalued
        overvalued = results_df[results_df['composite_z'] < -0.5].nsmallest(5, 'composite_z')
        if not overvalued.empty:
            print("\n🔴 TOP OVERVALUED:")
            for _, row in overvalued.iterrows():
                print(f"  {row['ticker']}: z={row['composite_z']:.2f}, conf={row['composite_confidence']:.2f}")
    
    print("\n✅ Valuation engines operational")
    return results_df

if __name__ == "__main__":
    main()