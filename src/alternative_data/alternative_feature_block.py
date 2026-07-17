"""
AlternativeFeatureBlock — Converts alternative data into model-ready features.

This is the only place in the system where alternative data math happens.
feature_factory.py (Research Engine) and data_pipeline.py (Intelligence Stack)
both call this block with the same IngestionRegistry and as_of_date.
They receive identical features, guaranteeing research-to-live consistency.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd
import numpy as np

from src.alternative_data.alt_data_keys import (
    BULK_ACCUMULATION_BREADTH,
    BULK_BREADTH,
    BULK_DISTRIBUTION_BREADTH,
    BULK_NET_BREADTH,
    BULK_NET_FLOW,
    BULK_SIGNAL_NUMERIC,
    CREDIT_NET_MOMENTUM,
    CREDIT_STRESS_FLAG,
    CREDIT_UPGRADE_RATIO,
    PLEDGE_MARKET_AVG,
    PLEDGE_SYSTEMIC_RISK,
    PLEDGE_TREND,
    POWER_DEVIATION_SEASONAL,
    POWER_INDUSTRIAL_PROXY,
    POWER_YOY_GROWTH,
)
# Lazy under TYPE_CHECKING to break the ingestion<->core<->alternative_data
# import cycle (2026-07-17): ingestion_registry -> fundamental_loader ->
# core.panel_math -> core.__init__ -> orchestrator -> state -> alternative_data
# -> this module -> ingestion_registry (half-built). Only used as an annotation.
if TYPE_CHECKING:
    from src.ingestion.ingestion_registry import IngestionRegistry

logger = logging.getLogger(__name__)


class AlternativeFeatureBlock:
    """Converts alternative data into model-ready features."""
    
    def __init__(self, registry: "IngestionRegistry", config: dict):
        self.registry = registry
        self.config = config
        
        # Feature configuration
        alt_config = config.get('alternative_data', {})
        self.high_pledge_threshold = alt_config.get('risk_thresholds', {}).get('high_pledge_threshold', 30.0)
        self.critical_pledge_threshold = alt_config.get('risk_thresholds', {}).get('critical_pledge_threshold', 50.0)
        self.gst_weight = alt_config.get('feature_weights', {}).get('gst_weight', 0.6)
        self.power_weight = alt_config.get('feature_weights', {}).get('power_weight', 0.4)
        
        logger.info("AlternativeFeatureBlock initialized")
    
    @classmethod
    def get_market_feature_names(cls) -> List[str]:
        """Return list of all market-level feature names."""
        return [
            # GST features
            'gst_mom_growth', 'gst_yoy_growth', 'gst_trend_accel',
            'gst_deviation_from_trend', 'gst_regime_numeric',
            # Power features
            POWER_YOY_GROWTH, POWER_DEVIATION_SEASONAL,
            'power_mom_change', POWER_INDUSTRIAL_PROXY,
            # Credit market features
            CREDIT_UPGRADE_RATIO, CREDIT_NET_MOMENTUM,
            CREDIT_STRESS_FLAG,
            # Bulk market features
            BULK_NET_FLOW, BULK_BREADTH,
            BULK_SIGNAL_NUMERIC, BULK_ACCUMULATION_BREADTH,
            BULK_DISTRIBUTION_BREADTH, BULK_NET_BREADTH,
            # Pledge market features
            PLEDGE_MARKET_AVG, PLEDGE_TREND,
            PLEDGE_SYSTEMIC_RISK
        ]
    
    @classmethod
    def get_company_feature_names(cls) -> List[str]:
        """Return list of all company-level feature names."""
        return [
            # Credit features
            'credit_current_rating_score', 'credit_rating_momentum_90d',
            'credit_in_distress', 'credit_watch_negative',
            # Bulk deal features
            'bulk_net_flow_30d', 'bulk_net_flow_90d',
            'bulk_accumulation_flag', 'bulk_distribution_flag',
            'bulk_has_recent_deal',
            # Pledge features
            'pledge_pct_current', 'pledge_change_qoq', 'pledge_change_yoy',
            'pledge_high_flag', 'pledge_increasing_2q', 'pledge_risk_score'
        ]
    
    def compute_market_level_features(self, as_of_date: datetime) -> pd.DataFrame:
        """Compute market-wide alternative data features."""
        features = {'Date': as_of_date}
        
        # GST Feature Group
        try:
            gst_features = self._compute_gst_features(as_of_date)
            features.update(gst_features)
        except Exception as e:
            logger.warning(f"GST feature computation failed: {e}")
            features.update(self._empty_gst_features())
        
        # Power Feature Group
        try:
            power_features = self._compute_power_features(as_of_date)
            features.update(power_features)
        except Exception as e:
            logger.warning(f"Power feature computation failed: {e}")
            features.update(self._empty_power_features())
        
        # Credit Market Feature Group
        try:
            credit_features = self._compute_credit_market_features(as_of_date)
            features.update(credit_features)
        except Exception as e:
            logger.warning(f"Credit market feature computation failed: {e}")
            features.update(self._empty_credit_market_features())
        
        # Smart Money Aggregate Feature Group
        try:
            bulk_features = self._compute_bulk_market_features(as_of_date)
            features.update(bulk_features)
        except Exception as e:
            logger.warning(f"Bulk market feature computation failed: {e}")
            features.update(self._empty_bulk_market_features())
        
        # Promoter Risk Aggregate Feature Group
        try:
            pledge_features = self._compute_pledge_market_features(as_of_date)
            features.update(pledge_features)
        except Exception as e:
            logger.warning(f"Pledge market feature computation failed: {e}")
            features.update(self._empty_pledge_market_features())
        
        return pd.DataFrame([features]).set_index('Date')
    
    def _compute_gst_features(self, as_of_date: datetime) -> Dict[str, float]:
        """
        Compute GST-based economic activity features.
        
        Returns z-scored features for model consumption.
        """
        try:
            gst_df = self.registry.alternative.load_gst(as_of_date)
            
            if gst_df.empty or len(gst_df) < 12:
                logger.warning("Insufficient GST data")
                return self._empty_gst_features()
            
            # Get latest available data point
            latest = gst_df.iloc[-1]
            
            # Extract raw features
            mom_growth = latest.get('gst_mom_growth', 0.0)
            yoy_growth = latest.get('gst_yoy_growth', 0.0)
            deviation = latest.get('gst_deviation_from_trend', 0.0)
            
            # Compute trend acceleration (2nd derivative)
            if len(gst_df) >= 3 and 'gst_mom_growth' in gst_df.columns:
                recent_mom = gst_df['gst_mom_growth'].iloc[-3:].values
                trend_accel = recent_mom[-1] - recent_mom[0] if len(recent_mom) == 3 else 0.0
            else:
                trend_accel = 0.0
            
            # Regime classification
            regime_numeric = self._classify_gst_regime(yoy_growth, deviation)
            
            # Z-score normalization using rolling history
            features = {
                'gst_mom_growth': self._zscore(mom_growth, gst_df.get('gst_mom_growth', pd.Series([0.0]))),
                'gst_yoy_growth': self._zscore(yoy_growth, gst_df.get('gst_yoy_growth', pd.Series([0.0]))),
                'gst_trend_accel': self._zscore(trend_accel, gst_df.get('gst_mom_growth', pd.Series([0.0])).diff()),
                'gst_deviation_from_trend': float(deviation),  # Already normalized
                'gst_regime_numeric': float(regime_numeric)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error computing GST features: {e}")
            return self._empty_gst_features()
    
    def _classify_gst_regime(self, yoy_growth: float, deviation: float) -> int:
        """Classify GST regime into numeric code."""
        if yoy_growth > 0.10 and deviation > 0.5:
            return 2  # EXPANSION
        elif yoy_growth > 0.05 and deviation > 0:
            return 1  # RECOVERING
        elif yoy_growth < -0.05 and deviation < -0.5:
            return -2  # CONTRACTION
        elif yoy_growth < 0 or deviation < -0.25:
            return -1  # SLOWING
        else:
            return 0  # NEUTRAL
    
    def _empty_gst_features(self) -> Dict[str, float]:
        """Return zero features when GST data unavailable."""
        return {
            'gst_mom_growth': 0.0,
            'gst_yoy_growth': 0.0,
            'gst_trend_accel': 0.0,
            'gst_deviation_from_trend': 0.0,
            'gst_regime_numeric': 0.0
        }
    
    def _compute_power_features(self, as_of_date: datetime) -> Dict[str, float]:
        """
        Compute power consumption features.
        
        Returns z-scored features indicating industrial activity.
        """
        try:
            power_df = self.registry.alternative.load_power_consumption(as_of_date)
            
            if power_df.empty or len(power_df) < 30:
                logger.warning("Insufficient power consumption data")
                return self._empty_power_features()
            
            # Get latest available data
            latest = power_df.iloc[-1]
            
            # Extract raw features
            yoy_growth = latest.get('power_yoy_growth', 0.0)
            deviation_seasonal = latest.get('power_deviation_from_seasonal', 0.0)
            
            # Month-over-month change
            if len(power_df) >= 2 and 'power_consumption' in power_df.columns:
                mom_change = power_df['power_consumption'].pct_change().iloc[-1]
            else:
                mom_change = 0.0
            
            # Industrial proxy: composite score
            industrial_proxy = self._compute_industrial_proxy(yoy_growth, deviation_seasonal, mom_change)
            
            # Z-score normalization
            features = {
                POWER_YOY_GROWTH: self._zscore(yoy_growth, power_df.get('power_yoy_growth', pd.Series([0.0]))),
                POWER_DEVIATION_SEASONAL: float(deviation_seasonal),  # Already normalized
                'power_mom_change': self._zscore(mom_change, power_df.get('power_consumption', pd.Series([0.0])).pct_change()),
                POWER_INDUSTRIAL_PROXY: float(industrial_proxy)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error computing power features: {e}")
            return self._empty_power_features()
    
    def _compute_industrial_proxy(self, yoy_growth: float, deviation: float, mom_change: float) -> float:
        """
        Compute composite industrial activity proxy score.
        
        Returns value between -1 and 1.
        """
        # Weighted combination
        score = (0.5 * np.clip(yoy_growth * 10, -1, 1) +
                0.3 * np.clip(deviation, -1, 1) +
                0.2 * np.clip(mom_change * 20, -1, 1))
        return float(np.clip(score, -1, 1))
    
    def _empty_power_features(self) -> Dict[str, float]:
        """Return zero features when power data unavailable."""
        return {
            POWER_YOY_GROWTH: 0.0,
            POWER_DEVIATION_SEASONAL: 0.0,
            'power_mom_change': 0.0,
            POWER_INDUSTRIAL_PROXY: 0.0
        }
    
    def _compute_credit_market_features(self, as_of_date: datetime) -> Dict[str, float]:
        """
        Compute market-wide credit rating features.
        
        Returns normalized credit stress indicators.
        """
        try:
            credit_df = self.registry.alternative.load_credit_ratings(as_of_date)
            
            if credit_df.empty:
                logger.warning("No credit ratings data available")
                return self._empty_credit_market_features()
            
            # Filter to last 90 days for momentum calculation
            start_date = as_of_date - timedelta(days=90)
            
            # Reset index to access ActionDate
            if isinstance(credit_df.index, pd.MultiIndex):
                credit_df = credit_df.reset_index()
            
            if 'ActionDate' in credit_df.columns:
                recent_df = credit_df[credit_df['ActionDate'] >= start_date]
            else:
                recent_df = credit_df
            
            # Count upgrades and downgrades
            if 'ActionType' in recent_df.columns:
                upgrades = (recent_df['ActionType'] == 'upgrade').sum()
                downgrades = (recent_df['ActionType'] == 'downgrade').sum()
                
                # Upgrade ratio
                total_actions = upgrades + downgrades
                upgrade_ratio = upgrades / total_actions if total_actions > 0 else 0.5
                
                # Net momentum (normalized)
                net_momentum = (upgrades - downgrades) / max(total_actions, 1)
            else:
                upgrade_ratio = 0.5
                net_momentum = 0.0
            
            # Stress flag: more downgrades than upgrades
            stress_flag = 1.0 if upgrade_ratio < 0.4 else 0.0
            
            features = {
                CREDIT_UPGRADE_RATIO: float(upgrade_ratio),
                CREDIT_NET_MOMENTUM: float(net_momentum),
                CREDIT_STRESS_FLAG: float(stress_flag)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error computing credit market features: {e}")
            return self._empty_credit_market_features()
    
    def _empty_credit_market_features(self) -> Dict[str, float]:
        """Return neutral features when credit data unavailable."""
        return {
            CREDIT_UPGRADE_RATIO: 0.5,
            CREDIT_NET_MOMENTUM: 0.0,
            CREDIT_STRESS_FLAG: 0.0
        }
    
    def _compute_bulk_market_features(self, as_of_date: datetime) -> Dict[str, float]:
        """
        Compute market-wide bulk deal (smart money) features.
        
        Returns normalized institutional flow indicators.
        """
        try:
            bulk_df = self.registry.alternative.load_bulk_deals(as_of_date, lookback_days=90)
            
            if bulk_df.empty:
                logger.warning("No bulk deals data available")
                return self._empty_bulk_market_features()
            
            # Aggregate market-wide metrics
            if 'net_buy_pressure' in bulk_df.columns:
                total_net_flow = bulk_df['net_buy_pressure'].sum()
                total_volume = bulk_df.get('total_volume', bulk_df['net_buy_pressure'].abs()).sum()
                
                # Normalize net flow
                net_flow_normalized = total_net_flow / max(total_volume, 1)
            else:
                net_flow_normalized = 0.0
            
            accumulation_breadth, distribution_breadth, net_breadth = self._compute_bulk_breadths(bulk_df)
            
            # Signal classification
            if net_flow_normalized > 0.3 and accumulation_breadth > 0.6:
                signal_numeric = 2  # STRONG_ACCUMULATION
            elif net_flow_normalized > 0.1 and accumulation_breadth > 0.5:
                signal_numeric = 1  # MILD_ACCUMULATION
            elif net_flow_normalized < -0.3 and distribution_breadth > 0.6:
                signal_numeric = -2  # STRONG_DISTRIBUTION
            elif net_flow_normalized < -0.1 and distribution_breadth > 0.5:
                signal_numeric = -1  # MILD_DISTRIBUTION
            else:
                signal_numeric = 0  # NEUTRAL
            
            features = {
                BULK_NET_FLOW: float(net_flow_normalized),
                BULK_BREADTH: float(net_breadth),
                BULK_ACCUMULATION_BREADTH: float(accumulation_breadth),
                BULK_DISTRIBUTION_BREADTH: float(distribution_breadth),
                BULK_NET_BREADTH: float(net_breadth),
                BULK_SIGNAL_NUMERIC: float(signal_numeric)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error computing bulk market features: {e}")
            return self._empty_bulk_market_features()
    
    def _empty_bulk_market_features(self) -> Dict[str, float]:
        """Return neutral features when bulk deal data unavailable."""
        return {
            BULK_NET_FLOW: 0.0,
            BULK_BREADTH: 0.0,
            BULK_ACCUMULATION_BREADTH: 0.0,
            BULK_DISTRIBUTION_BREADTH: 0.0,
            BULK_NET_BREADTH: 0.0,
            BULK_SIGNAL_NUMERIC: 0.0
        }
    
    def _compute_pledge_market_features(self, as_of_date: datetime) -> Dict[str, float]:
        """
        Compute market-wide promoter pledge features.
        
        Returns normalized pledge risk indicators.
        """
        try:
            pledge_df = self.registry.alternative.load_promoter_pledges(as_of_date)
            
            if pledge_df.empty:
                logger.warning("No promoter pledge data available")
                return self._empty_pledge_market_features()
            
            # Reset index to access columns
            if isinstance(pledge_df.index, pd.MultiIndex):
                pledge_df = pledge_df.reset_index()
            
            # Market average pledge percentage
            if 'PledgePct' in pledge_df.columns:
                # Get latest pledge for each ticker
                if 'Ticker' in pledge_df.columns and 'QuarterEnd' in pledge_df.columns:
                    latest_pledges = pledge_df.sort_values('QuarterEnd').groupby('Ticker').last()
                    market_avg = latest_pledges['PledgePct'].mean()
                else:
                    market_avg = pledge_df['PledgePct'].mean()
            else:
                market_avg = 0.0
            
            # Trend: compare current avg to 1 year ago
            if 'QuarterEnd' in pledge_df.columns and 'PledgePct' in pledge_df.columns:
                one_year_ago = as_of_date - timedelta(days=365)
                old_data = pledge_df[pledge_df['QuarterEnd'] <= one_year_ago]
                
                if not old_data.empty:
                    old_avg = old_data['PledgePct'].mean()
                    trend = (market_avg - old_avg) / max(old_avg, 1)
                else:
                    trend = 0.0
            else:
                trend = 0.0
            
            # Systemic risk: high percentage of companies with elevated pledge
            if 'high_pledge_flag' in pledge_df.columns:
                high_pledge_ratio = pledge_df['high_pledge_flag'].mean()
                systemic_risk = 1.0 if high_pledge_ratio > 0.25 else 0.0
            else:
                systemic_risk = 0.0
            
            features = {
                PLEDGE_MARKET_AVG: float(market_avg / 100.0),  # Normalize to 0-1
                PLEDGE_TREND: float(np.clip(trend, -1, 1)),
                PLEDGE_SYSTEMIC_RISK: float(systemic_risk)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error computing pledge market features: {e}")
            return self._empty_pledge_market_features()
    
    def _empty_pledge_market_features(self) -> Dict[str, float]:
        """Return neutral features when pledge data unavailable."""
        return {
            PLEDGE_MARKET_AVG: 0.0,
            PLEDGE_TREND: 0.0,
            PLEDGE_SYSTEMIC_RISK: 0.0
        }

    @staticmethod
    def _compute_bulk_breadths(bulk_df: pd.DataFrame) -> tuple[float, float, float]:
        """Compute accumulation, distribution, and net breadth for bulk deals."""
        if bulk_df is None or bulk_df.empty:
            return 0.0, 0.0, 0.0

        signed_series = None
        for candidate in ("signed_qty", "net_buy_pressure", "signed_value", "net_flow"):
            if candidate in bulk_df.columns:
                signed_series = pd.to_numeric(bulk_df[candidate], errors="coerce")
                break

        if signed_series is None:
            if "institutional_accumulation" in bulk_df.columns:
                accumulation_mask = bulk_df["institutional_accumulation"].fillna(False).astype(bool)
                distribution_mask = ~accumulation_mask
            else:
                return 0.0, 0.0, 0.0
        else:
            accumulation_mask = signed_series.fillna(0.0) > 0.0
            distribution_mask = signed_series.fillna(0.0) < 0.0

        total = max(int(len(bulk_df)), 1)
        accumulation_breadth = float(accumulation_mask.sum() / total)
        distribution_breadth = float(distribution_mask.sum() / total)
        net_breadth = float((accumulation_mask.sum() - distribution_mask.sum()) / total)
        return accumulation_breadth, distribution_breadth, net_breadth
    
    def compute_company_level_features(
        self,
        as_of_date: datetime,
        tickers: List[str]
    ) -> pd.DataFrame:
        """
        Compute per-ticker alternative data features.
        
        CRITICAL: Output must have exactly the same tickers as input,
        even if some have no coverage. Missing coverage = 0.0.
        
        Args:
            as_of_date: Point-in-time date
            tickers: List of ticker symbols
            
        Returns:
            DataFrame with Ticker as index and company-level feature columns
        """
        features_list = []
        
        for ticker in tickers:
            ticker_features = {'Ticker': ticker}
            
            # Credit features
            try:
                credit_features = self._compute_company_credit_features(as_of_date, ticker)
                ticker_features.update(credit_features)
            except Exception as e:
                logger.warning(f"Credit features failed for {ticker}: {e}")
                ticker_features.update(self._empty_company_credit_features())
            
            # Bulk deal features
            try:
                bulk_features = self._compute_company_bulk_features(as_of_date, ticker)
                ticker_features.update(bulk_features)
            except Exception as e:
                logger.warning(f"Bulk features failed for {ticker}: {e}")
                ticker_features.update(self._empty_company_bulk_features())
            
            # Pledge features
            try:
                pledge_features = self._compute_company_pledge_features(as_of_date, ticker)
                ticker_features.update(pledge_features)
            except Exception as e:
                logger.warning(f"Pledge features failed for {ticker}: {e}")
                ticker_features.update(self._empty_company_pledge_features())
            
            features_list.append(ticker_features)
        
        features_df = pd.DataFrame(features_list)
        features_df = features_df.set_index('Ticker')
        
        # Ensure all input tickers are present
        for ticker in tickers:
            if ticker not in features_df.index:
                features_df.loc[ticker] = {
                    **self._empty_company_credit_features(),
                    **self._empty_company_bulk_features(),
                    **self._empty_company_pledge_features()
                }
        
        return features_df
    
    def _compute_company_credit_features(self, as_of_date: datetime, ticker: str) -> Dict[str, float]:
        """Compute credit rating features for a single company."""
        try:
            credit_df = self.registry.alternative.load_credit_ratings(as_of_date, tickers=[ticker])
            
            if credit_df.empty:
                return self._empty_company_credit_features()
            
            # Reset index
            if isinstance(credit_df.index, pd.MultiIndex):
                credit_df = credit_df.reset_index()
            
            # Get latest rating
            if 'CurrentRating' in credit_df.columns:
                latest_rating = credit_df.iloc[-1]['CurrentRating']
                rating_score = self._rating_to_score(latest_rating)
            else:
                rating_score = 0.0
            
            # 90-day momentum
            if 'rating_momentum' in credit_df.columns:
                momentum_90d = credit_df.iloc[-1].get('rating_momentum', 0.0)
            else:
                momentum_90d = 0.0
            
            # Distress flag
            if 'in_distress' in credit_df.columns:
                in_distress = float(credit_df.iloc[-1].get('in_distress', False))
            else:
                in_distress = 0.0
            
            # Watch negative (recent downgrade)
            if 'ActionType' in credit_df.columns and 'ActionDate' in credit_df.columns:
                recent_actions = credit_df[credit_df['ActionDate'] >= (as_of_date - timedelta(days=30))]
                watch_negative = 1.0 if (recent_actions['ActionType'] == 'downgrade').any() else 0.0
            else:
                watch_negative = 0.0
            
            return {
                'credit_current_rating_score': float(rating_score),
                'credit_rating_momentum_90d': float(momentum_90d),
                'credit_in_distress': float(in_distress),
                'credit_watch_negative': float(watch_negative)
            }
            
        except Exception as e:
            logger.warning(f"Error computing credit features for {ticker}: {e}")
            return self._empty_company_credit_features()
    
    def _rating_to_score(self, rating: str) -> float:
        """Convert credit rating to numeric score (-1 to 1)."""
        rating_map = {
            'AAA': 1.0, 'AA+': 0.9, 'AA': 0.8, 'AA-': 0.7,
            'A+': 0.6, 'A': 0.5, 'A-': 0.4,
            'BBB+': 0.3, 'BBB': 0.2, 'BBB-': 0.1,
            'BB+': 0.0, 'BB': -0.1, 'BB-': -0.2,
            'B+': -0.3, 'B': -0.4, 'B-': -0.5,
            'C': -0.7, 'D': -1.0
        }
        return rating_map.get(rating, 0.0)
    
    def _empty_company_credit_features(self) -> Dict[str, float]:
        """Return neutral credit features."""
        return {
            'credit_current_rating_score': 0.0,
            'credit_rating_momentum_90d': 0.0,
            'credit_in_distress': 0.0,
            'credit_watch_negative': 0.0
        }
    
    def _compute_company_bulk_features(self, as_of_date: datetime, ticker: str) -> Dict[str, float]:
        """Compute bulk deal features for a single company."""
        try:
            # 30-day lookback
            bulk_30d = self.registry.alternative.load_bulk_deals(as_of_date, tickers=[ticker], lookback_days=30)
            # 90-day lookback
            bulk_90d = self.registry.alternative.load_bulk_deals(as_of_date, tickers=[ticker], lookback_days=90)
            
            # 30-day net flow
            if not bulk_30d.empty and 'net_buy_pressure' in bulk_30d.columns:
                net_flow_30d = bulk_30d['net_buy_pressure'].sum()
                total_volume_30d = bulk_30d.get('total_volume', bulk_30d['net_buy_pressure'].abs()).sum()
                net_flow_30d_normalized = net_flow_30d / max(total_volume_30d, 1)
            else:
                net_flow_30d_normalized = 0.0
            
            # 90-day net flow
            if not bulk_90d.empty and 'net_buy_pressure' in bulk_90d.columns:
                net_flow_90d = bulk_90d['net_buy_pressure'].sum()
                total_volume_90d = bulk_90d.get('total_volume', bulk_90d['net_buy_pressure'].abs()).sum()
                net_flow_90d_normalized = net_flow_90d / max(total_volume_90d, 1)
            else:
                net_flow_90d_normalized = 0.0
            
            # Accumulation/distribution flags
            accumulation_flag = 1.0 if net_flow_90d_normalized > 0.2 else 0.0
            distribution_flag = 1.0 if net_flow_90d_normalized < -0.2 else 0.0
            
            # Recent deal flag
            has_recent_deal = 1.0 if not bulk_30d.empty else 0.0
            
            return {
                'bulk_net_flow_30d': float(net_flow_30d_normalized),
                'bulk_net_flow_90d': float(net_flow_90d_normalized),
                'bulk_accumulation_flag': float(accumulation_flag),
                'bulk_distribution_flag': float(distribution_flag),
                'bulk_has_recent_deal': float(has_recent_deal)
            }
            
        except Exception as e:
            logger.warning(f"Error computing bulk features for {ticker}: {e}")
            return self._empty_company_bulk_features()
    
    def _empty_company_bulk_features(self) -> Dict[str, float]:
        """Return neutral bulk deal features."""
        return {
            'bulk_net_flow_30d': 0.0,
            'bulk_net_flow_90d': 0.0,
            'bulk_accumulation_flag': 0.0,
            'bulk_distribution_flag': 0.0,
            'bulk_has_recent_deal': 0.0
        }
    
    def _compute_company_pledge_features(self, as_of_date: datetime, ticker: str) -> Dict[str, float]:
        """Compute promoter pledge features for a single company."""
        try:
            pledge_df = self.registry.alternative.load_promoter_pledges(as_of_date, tickers=[ticker])
            
            if pledge_df.empty:
                return self._empty_company_pledge_features()
            
            # Reset index
            if isinstance(pledge_df.index, pd.MultiIndex):
                pledge_df = pledge_df.reset_index()
            
            # Sort by quarter
            if 'QuarterEnd' in pledge_df.columns:
                pledge_df = pledge_df.sort_values('QuarterEnd')
            
            # Current pledge percentage
            if 'PledgePct' in pledge_df.columns:
                current_pledge = pledge_df.iloc[-1]['PledgePct']
            else:
                current_pledge = 0.0
            
            # QoQ change
            if 'pledge_change_qoq' in pledge_df.columns:
                change_qoq = pledge_df.iloc[-1].get('pledge_change_qoq', 0.0)
            elif len(pledge_df) >= 2 and 'PledgePct' in pledge_df.columns:
                change_qoq = pledge_df['PledgePct'].iloc[-1] - pledge_df['PledgePct'].iloc[-2]
            else:
                change_qoq = 0.0
            
            # YoY change
            if len(pledge_df) >= 4 and 'PledgePct' in pledge_df.columns:
                change_yoy = pledge_df['PledgePct'].iloc[-1] - pledge_df['PledgePct'].iloc[-4]
            else:
                change_yoy = 0.0
            
            # High pledge flag
            high_flag = 1.0 if current_pledge > self.high_pledge_threshold else 0.0
            
            # Increasing 2 quarters flag
            if 'pledge_increasing' in pledge_df.columns:
                increasing_2q = float(pledge_df.iloc[-1].get('pledge_increasing', False))
            else:
                increasing_2q = 0.0
            
            # Risk score (composite)
            risk_score = self._compute_pledge_risk_score(current_pledge, change_qoq, change_yoy)
            
            return {
                'pledge_pct_current': float(current_pledge / 100.0),  # Normalize to 0-1
                'pledge_change_qoq': float(change_qoq / 100.0),
                'pledge_change_yoy': float(change_yoy / 100.0),
                'pledge_high_flag': float(high_flag),
                'pledge_increasing_2q': float(increasing_2q),
                'pledge_risk_score': float(risk_score)
            }
            
        except Exception as e:
            logger.warning(f"Error computing pledge features for {ticker}: {e}")
            return self._empty_company_pledge_features()
    
    def _compute_pledge_risk_score(self, current: float, qoq: float, yoy: float) -> float:
        """
        Compute composite pledge risk score.
        
        Returns value between 0 (no risk) and 1 (high risk).
        """
        # Level risk
        level_risk = np.clip(current / 100.0, 0, 1)
        
        # Trend risk (increasing is bad)
        trend_risk = np.clip((qoq + yoy) / 50.0, 0, 1)
        
        # Weighted combination
        risk_score = 0.6 * level_risk + 0.4 * trend_risk
        
        return float(np.clip(risk_score, 0, 1))
    
    def _empty_company_pledge_features(self) -> Dict[str, float]:
        """Return neutral pledge features."""
        return {
            'pledge_pct_current': 0.0,
            'pledge_change_qoq': 0.0,
            'pledge_change_yoy': 0.0,
            'pledge_high_flag': 0.0,
            'pledge_increasing_2q': 0.0,
            'pledge_risk_score': 0.0
        }
    
    def _zscore(self, value: float, series: pd.Series) -> float:
        """
        Compute robust z-score for a value against a series.
        
        Uses median and MAD for robustness against outliers.
        
        Args:
            value: Value to normalize
            series: Historical series for context
            
        Returns:
            Z-scored value (0.0 if insufficient data)
        """
        try:
            if len(series) < 10:
                return 0.0
            
            # Use median and MAD for robustness
            median = series.median()
            mad = (series - median).abs().median()
            
            if mad == 0 or np.isnan(mad):
                return 0.0
            
            # Z-score using MAD (scaled to match std)
            zscore = (value - median) / (1.4826 * mad)
            
            # Clip to reasonable range
            return float(np.clip(zscore, -3, 3))
            
        except Exception as e:
            logger.warning(f"Error computing z-score: {e}")
            return 0.0
