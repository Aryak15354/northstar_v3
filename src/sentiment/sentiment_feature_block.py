"""
SentimentFeatureBlock — Converts raw sentiment scores into model-ready features.

This is the only place in the system where sentiment math happens. feature_factory.py
in the Research Engine and data_pipeline.py in the Intelligence Stack both call this block.
They receive identical features. This guarantees that research experiments and live signal
generation use the same sentiment representation.

The feature block follows the same pattern as other feature blocks in the system.
It accepts an IngestionRegistry and an as_of_date, and returns a DataFrame with
(Ticker, Date) as the index and feature columns ready for model consumption.
"""

import logging
import warnings
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class SentimentStalenessWarning(UserWarning):
    """Warning emitted when sentiment data is stale."""
    pass


class SentimentFeatureBlock:
    """
    Feature engineering layer for sentiment data.
    
    Converts raw sentiment scores into normalized, model-ready features
    with strict PIT enforcement and graceful degradation.
    """
    
    def __init__(self, registry, config: dict = None):
        """
        Initialize feature block.
        
        Args:
            registry: IngestionRegistry instance
            config: Configuration dict with sentiment_features section
        """
        self.registry = registry
        self.config = config or {}
        
        # Feature configuration
        feature_config = self.config.get('sentiment_features', {})
        self.lookback_252d = feature_config.get('lookback_252d', 252)
        self.lookback_30d = feature_config.get('lookback_30d', 30)
        self.lookback_7d = feature_config.get('lookback_7d', 7)

    @staticmethod
    def _standardize_series(
        values: pd.Series,
        rolling_mean: pd.Series,
        rolling_std: pd.Series,
    ) -> pd.Series:
        """
        Standardize a series, but preserve directional signal when variance collapses.
        """
        std_safe = pd.to_numeric(rolling_std, errors="coerce")
        standardized = (values - rolling_mean) / std_safe.replace(0, np.nan)
        fallback_mask = std_safe.isna() | std_safe.eq(0) | rolling_mean.isna()
        return standardized.where(~fallback_mask, values)

    @classmethod
    def _latest_standardized_value(
        cls,
        values: pd.Series,
        rolling_mean: pd.Series,
        rolling_std: pd.Series,
    ) -> float:
        standardized = cls._standardize_series(values, rolling_mean, rolling_std)
        latest = pd.to_numeric(standardized.iloc[-1], errors="coerce")
        return 0.0 if pd.isna(latest) else float(latest)
    
    @classmethod
    def get_feature_names(cls) -> List[str]:
        """
        Return canonical list of all feature column names this block produces.
        
        Called by feature_factory.py to register the feature budget.
        
        Returns:
            List of feature column names
        """
        market_features = [
            'sent_market_score_1d',
            'sent_market_score_7d',
            'sent_market_score_30d',
            'sent_market_momentum',
            'sent_market_volatility',
            'sent_regime_numeric',
            'sent_crisis_proximity',
            'sent_price_divergence'
        ]
        
        company_features = [
            'sent_company_score_7d',
            'sent_company_score_30d',
            'sent_company_momentum',
            'sent_company_vs_market',
            'sent_coverage_density',
            'sent_has_coverage'
        ]
        
        return market_features + company_features
    
    def compute_market_features(self, as_of_date: datetime) -> pd.DataFrame:
        """
        Compute market-level sentiment features.
        
        CRITICAL: All features use only data up to T-1 (yesterday).
        Never use today's sentiment.
        
        Args:
            as_of_date: Point-in-time date (today)
            
        Returns:
            DataFrame with Date as index and market sentiment feature columns
        """
        try:
            # Check freshness first
            if not self.registry.sentiment.is_sentiment_fresh(as_of_date):
                lag_days = self._get_data_lag_days(as_of_date)
                warnings.warn(
                    f"Sentiment data is {lag_days} days stale. Returning neutral features.",
                    SentimentStalenessWarning
                )
                return self._neutral_market_features(as_of_date)
            
            # Load market sentiment
            market_df = self.registry.sentiment.load_market_sentiment(as_of_date)
            
            if market_df.empty:
                logger.warning("No market sentiment data available")
                return self._neutral_market_features(as_of_date)
            
            # Find score column
            if 'sentiment_score' in market_df.columns:
                score_col = 'sentiment_score'
            elif 'raw_score' in market_df.columns:
                score_col = 'raw_score'
            else:
                score_cols = [c for c in market_df.columns if 'score' in c.lower()]
                if not score_cols:
                    logger.error("No sentiment score column found")
                    return self._neutral_market_features(as_of_date)
                score_col = score_cols[0]
            
            # Ensure we have enough history
            if len(market_df) < 30:
                logger.warning(f"Insufficient sentiment history: {len(market_df)} days")
                return self._neutral_market_features(as_of_date)
            
            # PIT enforcement: shift by 1 day (use yesterday's sentiment)
            scores = market_df[score_col].shift(1)
            
            # Compute z-scores using rolling window
            rolling_mean = scores.rolling(window=self.lookback_252d, min_periods=30).mean()
            rolling_std = scores.rolling(window=self.lookback_252d, min_periods=30).std()
            
            # sent_market_score_1d: yesterday's z-scored sentiment
            zscore_1d = self._standardize_series(scores, rolling_mean, rolling_std)
            
            # sent_market_score_7d: 7-day rolling mean, z-scored
            score_7d = scores.rolling(window=self.lookback_7d, min_periods=1).mean()
            zscore_7d = self._standardize_series(score_7d, rolling_mean, rolling_std)
            
            # sent_market_score_30d: 30-day rolling mean, z-scored
            score_30d = scores.rolling(window=self.lookback_30d, min_periods=7).mean()
            zscore_30d = self._standardize_series(score_30d, rolling_mean, rolling_std)
            
            # sent_market_momentum: 7d - 30d
            momentum = zscore_7d - zscore_30d
            
            # sent_market_volatility: 30-day std of daily sentiment
            volatility = scores.rolling(window=self.lookback_30d, min_periods=7).std()
            
            # sent_regime_numeric: encode regime as numeric
            # For this we need to classify regime
            from .sentiment_regime import SentimentRegimeClassifier
            from .sentiment_state import SentimentRegime
            
            classifier = SentimentRegimeClassifier(self.config)
            regime, _ = classifier.classify(scores.dropna(), as_of_date)
            
            regime_numeric_map = {
                SentimentRegime.PANIC: -2,
                SentimentRegime.FEAR: -1,
                SentimentRegime.NEUTRAL: 0,
                SentimentRegime.OPTIMISM: 1,
                SentimentRegime.EUPHORIA: 2,
                SentimentRegime.UNAVAILABLE: 0
            }
            regime_numeric = regime_numeric_map[regime]
            
            # sent_crisis_proximity: distance from PANIC threshold (-2.0)
            panic_threshold = -2.0
            crisis_proximity = np.maximum(0, (panic_threshold - zscore_1d) / abs(panic_threshold))
            crisis_proximity = np.clip(crisis_proximity, 0, 1)
            
            # sent_price_divergence: sentiment vs price action divergence
            # This requires price data - load it
            try:
                price_df = self.registry.market.load(as_of_date, tickers=['^NSEI'])
                if not price_df.empty and 'Close' in price_df.columns:
                    price_returns_5d = price_df['Close'].pct_change(5)
                    sentiment_momentum_5d = scores.rolling(5).mean().diff(5)
                    
                    # Divergence: opposite signs
                    price_sign = np.sign(price_returns_5d)
                    sent_sign = np.sign(sentiment_momentum_5d)
                    divergence = (price_sign != sent_sign).astype(float)
                else:
                    divergence = pd.Series(0.0, index=scores.index)
            except Exception as e:
                logger.warning(f"Could not compute price divergence: {e}")
                divergence = pd.Series(0.0, index=scores.index)
            
            # Assemble features
            features_df = pd.DataFrame({
                'sent_market_score_1d': zscore_1d,
                'sent_market_score_7d': zscore_7d,
                'sent_market_score_30d': zscore_30d,
                'sent_market_momentum': momentum,
                'sent_market_volatility': volatility,
                'sent_regime_numeric': regime_numeric,
                'sent_crisis_proximity': crisis_proximity,
                'sent_price_divergence': divergence
            })
            
            # Fill NaN with 0.0 (neutral)
            features_df = features_df.fillna(0.0)
            
            # Return only up to as_of_date
            features_df = features_df[features_df.index <= as_of_date]
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error computing market sentiment features: {e}", exc_info=True)
            return self._neutral_market_features(as_of_date)
    
    def compute_company_features(
        self,
        as_of_date: datetime,
        tickers: List[str]
    ) -> pd.DataFrame:
        """
        Compute per-ticker sentiment features.
        
        CRITICAL: Output must have exactly the same tickers as input,
        even if some have no sentiment coverage. Missing coverage = 0.0.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of ticker symbols
            
        Returns:
            DataFrame with Ticker as index and company sentiment feature columns
        """
        try:
            # Check freshness
            if not self.registry.sentiment.is_sentiment_fresh(as_of_date):
                return self._neutral_company_features(tickers)
            
            # Load company sentiment
            company_df = self.registry.sentiment.load_company_sentiment(
                as_of_date,
                tickers=tickers,
                lookback_days=90  # Need history for rolling calculations
            )
            
            if company_df.empty:
                logger.warning("No company sentiment data available")
                return self._neutral_company_features(tickers)
            
            # Load market sentiment for comparison
            market_df = self.registry.sentiment.load_market_sentiment(as_of_date)
            
            # Find score column
            if 'sentiment_score' in company_df.columns:
                score_col = 'sentiment_score'
            elif 'raw_score' in company_df.columns:
                score_col = 'raw_score'
            else:
                score_cols = [c for c in company_df.columns if 'score' in c.lower()]
                if not score_cols:
                    return self._neutral_company_features(tickers)
                score_col = score_cols[0]
            
            # Reset index to work with Ticker grouping
            if isinstance(company_df.index, pd.MultiIndex):
                company_df = company_df.reset_index()
            
            # Compute per-company features
            features_list = []
            
            for ticker in tickers:
                ticker_data = company_df[company_df['Ticker'] == ticker]
                
                if ticker_data.empty or len(ticker_data) < 7:
                    # No coverage for this ticker
                    features_list.append({
                        'Ticker': ticker,
                        'sent_company_score_7d': 0.0,
                        'sent_company_score_30d': 0.0,
                        'sent_company_momentum': 0.0,
                        'sent_company_vs_market': 0.0,
                        'sent_coverage_density': 0.0,
                        'sent_has_coverage': 0.0
                    })
                    continue
                
                # Sort by date
                ticker_data = ticker_data.sort_values('Date')
                scores = ticker_data[score_col]
                
                # Compute per-company z-scores (normalized against own history)
                mean = scores.rolling(window=self.lookback_252d, min_periods=30).mean()
                std = scores.rolling(window=self.lookback_252d, min_periods=30).std()
                
                # sent_company_score_7d: 7-day rolling, z-scored
                score_7d = scores.rolling(window=7, min_periods=1).mean()
                zscore_7d = self._latest_standardized_value(score_7d, mean, std)
                
                # sent_company_score_30d: 30-day rolling, z-scored
                score_30d = scores.rolling(window=30, min_periods=7).mean()
                zscore_30d = self._latest_standardized_value(score_30d, mean, std)
                
                # sent_company_momentum: 7d - 30d
                momentum = zscore_7d - zscore_30d
                
                # sent_company_vs_market: company z-score minus market z-score
                if not market_df.empty and score_col in market_df.columns:
                    market_scores = market_df[score_col]
                    market_score_7d = market_scores.rolling(window=7, min_periods=1).mean()
                    market_mean = market_scores.rolling(window=self.lookback_252d, min_periods=30).mean()
                    market_std = market_scores.rolling(window=self.lookback_252d, min_periods=30).std()
                    market_zscore = self._latest_standardized_value(market_score_7d, market_mean, market_std)
                    company_vs_market = zscore_7d - market_zscore
                else:
                    company_vs_market = 0.0
                
                # sent_coverage_density: article count in past 30 days, z-scored
                if 'article_count' in ticker_data.columns:
                    article_counts = ticker_data['article_count'].rolling(window=30, min_periods=1).sum()
                    count_mean = article_counts.rolling(window=self.lookback_252d, min_periods=30).mean()
                    count_std = article_counts.rolling(window=self.lookback_252d, min_periods=30).std()
                    coverage_density = self._latest_standardized_value(article_counts, count_mean, count_std)
                else:
                    coverage_density = 0.0
                
                # sent_has_coverage: boolean indicating recent coverage
                recent_data = ticker_data[ticker_data['Date'] >= (as_of_date - timedelta(days=14))]
                has_coverage = 1.0 if len(recent_data) > 0 else 0.0
                
                features_list.append({
                    'Ticker': ticker,
                    'sent_company_score_7d': float(zscore_7d),
                    'sent_company_score_30d': float(zscore_30d),
                    'sent_company_momentum': float(momentum),
                    'sent_company_vs_market': float(company_vs_market),
                    'sent_coverage_density': float(coverage_density),
                    'sent_has_coverage': float(has_coverage)
                })
            
            features_df = pd.DataFrame(features_list)
            features_df = features_df.set_index('Ticker')
            
            # Ensure all input tickers are present
            for ticker in tickers:
                if ticker not in features_df.index:
                    features_df.loc[ticker] = {
                        'sent_company_score_7d': 0.0,
                        'sent_company_score_30d': 0.0,
                        'sent_company_momentum': 0.0,
                        'sent_company_vs_market': 0.0,
                        'sent_coverage_density': 0.0,
                        'sent_has_coverage': 0.0
                    }
            
            return features_df
            
        except Exception as e:
            logger.error(f"Error computing company sentiment features: {e}", exc_info=True)
            return self._neutral_company_features(tickers)
    
    def _neutral_market_features(self, as_of_date: datetime) -> pd.DataFrame:
        """Return neutral (zero) market features when sentiment unavailable."""
        return pd.DataFrame({
            'sent_market_score_1d': [0.0],
            'sent_market_score_7d': [0.0],
            'sent_market_score_30d': [0.0],
            'sent_market_momentum': [0.0],
            'sent_market_volatility': [0.0],
            'sent_regime_numeric': [0],
            'sent_crisis_proximity': [0.0],
            'sent_price_divergence': [0.0]
        }, index=[as_of_date])
    
    def _neutral_company_features(self, tickers: List[str]) -> pd.DataFrame:
        """Return neutral (zero) company features when sentiment unavailable."""
        return pd.DataFrame({
            'Ticker': tickers,
            'sent_company_score_7d': 0.0,
            'sent_company_score_30d': 0.0,
            'sent_company_momentum': 0.0,
            'sent_company_vs_market': 0.0,
            'sent_coverage_density': 0.0,
            'sent_has_coverage': 0.0
        }).set_index('Ticker')
    
    def _get_data_lag_days(self, as_of_date: datetime) -> int:
        """Calculate how many days stale the sentiment data is."""
        try:
            market_df = self.registry.sentiment.load_market_sentiment(as_of_date)
            if not market_df.empty:
                latest_date = market_df.index.max()
                if isinstance(latest_date, pd.Timestamp):
                    latest_date = latest_date.to_pydatetime()
                return (as_of_date - latest_date).days
        except:
            pass
        return 999
